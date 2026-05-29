import asyncio
import json
import operator
import traceback
import uuid
from contextvars import ContextVar
from typing import Annotated, List, TypedDict

import httpx
import mlflow
from langgraph.graph import END, START, StateGraph
from mlflow.tracing import get_tracing_context_headers_for_http_request

from app.campaign_store import CampaignStore
from app.schemas import (
    CampaignRequest, CampaignData, CampaignStatus,
    CustomerProfile, CAMPAIGN_THEMES
)
from app.settings import settings
from app.vertical_config import brand

_auth_header: ContextVar[str] = ContextVar("_auth_header", default="")

campaigns_store = CampaignStore()
campaigns_store.init(settings.CAMPAIGN_STORAGE_PATH)


class CampaignState(TypedDict):
    campaign_id: str
    campaign_name: str
    campaign_description: str
    hotel_name: str
    target_audience: str
    theme: str
    start_date: str
    end_date: str
    status: str
    landing_page_html: str
    hero_image_url: str
    preview_url: str
    production_url: str
    email_subject_en: str
    email_body_en: str
    email_subject_zh: str
    email_body_zh: str
    customer_list: List[dict]
    customer_count: int
    error_message: str
    messages: Annotated[list, operator.add]


async def call_a2a_agent(agent_url: str, skill: str, params: dict) -> dict:
    from a2a.client import create_client, ClientConfig
    from a2a.types import SendMessageRequest, Message, Part, Role

    request = SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            message_id=uuid.uuid4().hex,
            parts=[Part(text=json.dumps({"skill": skill, **params}))],
        ),
    )
    timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
    headers = {}
    auth = _auth_header.get("")
    if auth:
        headers["Authorization"] = auth
    try:
        trace_headers = get_tracing_context_headers_for_http_request()
        headers.update(trace_headers)
    except Exception:
        pass
    config = ClientConfig(httpx_client=httpx.AsyncClient(timeout=timeout, headers=headers))
    client = await create_client(agent_url, client_config=config)

    try:
        last_task = None
        artifacts = []
        async for event in client.send_message(request):
            if event.HasField("task"):
                last_task = event.task
            elif event.HasField("artifact_update"):
                artifacts.append(event.artifact_update.artifact)

        all_artifacts = list(last_task.artifacts) if last_task and last_task.artifacts else []
        if not all_artifacts:
            all_artifacts = artifacts

        for artifact in all_artifacts:
            for part in artifact.parts:
                if part.text:
                    try:
                        parsed = json.loads(part.text)
                        print(f"[Campaign Director] A2A {skill} → {agent_url}: {parsed}")
                        return parsed
                    except json.JSONDecodeError:
                        return {"status": "success", "content": part.text}

        print(f"[Campaign Director] A2A {skill} → {agent_url}: no artifact! task_artifacts={len(last_task.artifacts) if last_task and last_task.artifacts else 0}, stream_artifacts={len(artifacts)}")
    finally:
        await client.close()

    return {"status": "error", "error": "No artifact returned from agent"}


async def publish_event(campaign_id: str, event_type: str, agent: str, task: str, data: dict = None):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.EVENT_HUB_URL}/events/{campaign_id}/publish",
                json={"event_type": event_type, "agent": agent, "task": task, "data": data or {}},
                timeout=5.0
            )
    except Exception as e:
        print(f"[Campaign Director] Failed to publish event: {type(e).__name__}: {e}")


async def _cleanup_k8s_resources(campaign_id: str):
    try:
        result = await call_a2a_agent(settings.DELIVERY_MANAGER_URL, "cleanup_campaign", {
            "campaign_id": campaign_id,
        })
        print(f"[Campaign Director] Cleanup result: {result}")
    except Exception as e:
        print(f"[Campaign Director] Cleanup via Delivery Manager failed: {e}")


async def validate_policy_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director", "Checking campaign policies...")
    try:
        result = await call_a2a_agent(settings.POLICY_GUARDIAN_URL, "validate_campaign", {
            "campaign_id": state["campaign_id"],
            "campaign_name": state["campaign_name"],
            "campaign_description": state["campaign_description"],
        })
        if result.get("approved") is False:
            state["error_message"] = f"Policy violation: {result.get('reason', 'Unknown')}"
            state["status"] = "failed"
            state["messages"] = [{"role": "assistant", "agent": "Policy Guardian",
                                  "content": f"Rejected: {result.get('reason', '')}"}]
        else:
            state["messages"] = [{"role": "assistant", "agent": "Policy Guardian",
                                  "content": "Campaign policies approved"}]
    except Exception:
        state["messages"] = [{"role": "assistant", "agent": "Policy Guardian",
                              "content": "Policy check skipped (service unavailable)"}]
    return state


async def generate_landing_page_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director",
                        "Starting creative design...", {"step": "generating_landing_page"})
    result = await call_a2a_agent(settings.CREATIVE_PRODUCER_URL, "generate_landing_page", {
        "campaign_id": state["campaign_id"],
        "campaign_name": state["campaign_name"],
        "campaign_description": state["campaign_description"],
        "hotel_name": state["hotel_name"],
        "theme": state["theme"],
        "start_date": state["start_date"],
        "end_date": state["end_date"]
    })
    if result.get("status") == "error":
        state["error_message"] = result.get("error", "Unknown error")
        state["status"] = "failed"
    else:
        state["landing_page_html"] = result.get("html", "")
        state["hero_image_url"] = result.get("hero_image_url", "") or ""
        state["messages"] = [{"role": "assistant", "agent": "Creative Producer",
                              "content": "Landing page generated successfully"}]
    return state


async def deploy_preview_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director",
                        "Publishing preview...", {"step": "deploying_preview"})
    try:
        campaign_info = json.dumps({
            "campaign_name": state["campaign_name"],
            "hotel_name": state["hotel_name"],
            "theme": state["theme"],
        })
        result = await call_a2a_agent(settings.DELIVERY_MANAGER_URL, "deploy_preview", {
            "campaign_id": state["campaign_id"],
            "html_content": state["landing_page_html"],
            "namespace": settings.DEV_NAMESPACE,
            "customers_json": json.dumps(state.get("customer_list", [])),
            "campaign_json": campaign_info,
        })
        print(f"[Campaign Director] deploy_preview A2A result: {result}")
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            if "Kubernetes" in error_msg:
                state["preview_url"] = f"local://preview/{state['campaign_id']}"
                state["status"] = "preview_ready"
                state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                                      "content": "Preview ready (local mode - K8s deployment skipped)"}]
            else:
                state["error_message"] = error_msg
                state["status"] = "failed"
        else:
            state["preview_url"] = result.get("preview_url", "")
            state["status"] = "preview_ready"
            state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                                  "content": f"Preview deployed at {state['preview_url']}"}]
    except Exception:
        state["preview_url"] = f"local://preview/{state['campaign_id']}"
        state["status"] = "preview_ready"
        state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                              "content": "Preview ready (local mode)"}]
    return state


async def retrieve_customers_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director",
                        "Finding your target audience...", {"step": "retrieving_customers"})
    result = await call_a2a_agent(settings.CUSTOMER_ANALYST_URL, "get_target_customers", {
        "campaign_id": state["campaign_id"],
        "target_audience": state["target_audience"],
        "limit": 50
    })
    if result.get("status") == "error":
        state["error_message"] = result.get("error", "Unknown error")
        state["status"] = "failed"
    else:
        state["customer_list"] = result.get("customers", [])
        state["customer_count"] = result.get("count", 0)
        state["messages"] = [{"role": "assistant", "agent": "Customer Analyst",
                              "content": f"Retrieved {state['customer_count']} {result.get('recipient_type', 'customers')}"}]
    return state


async def generate_email_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director",
                        "Crafting personalized emails...", {"step": "generating_email"})
    result = await call_a2a_agent(settings.DELIVERY_MANAGER_URL, "generate_email", {
        "campaign_id": state["campaign_id"],
        "campaign_name": state["campaign_name"],
        "campaign_description": state["campaign_description"],
        "hotel_name": state["hotel_name"],
        "campaign_url": state["preview_url"],
        "target_audience": state["target_audience"],
        "start_date": state["start_date"],
        "end_date": state["end_date"]
    })
    if result.get("status") == "error":
        state["error_message"] = result.get("error", "Unknown error")
        state["status"] = "failed"
    else:
        state["email_subject_en"] = result.get("email_subject_en", "")
        state["email_body_en"] = result.get("email_body_en", "")
        state["email_subject_zh"] = result.get("email_subject_zh", "")
        state["email_body_zh"] = result.get("email_body_zh", "")
        state["status"] = "email_ready"
        state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                              "content": "Email content generated in English and Chinese"}]
    return state


async def deploy_production_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director",
                        "Deploying campaign...", {"step": "deploying_production"})
    try:
        campaign_info = json.dumps({
            "campaign_name": state["campaign_name"],
            "hotel_name": state["hotel_name"],
            "theme": state["theme"],
        })
        result = await call_a2a_agent(settings.DELIVERY_MANAGER_URL, "deploy_production", {
            "campaign_id": state["campaign_id"],
            "html_content": state["landing_page_html"],
            "namespace": settings.PROD_NAMESPACE,
            "customers_json": json.dumps(state.get("customer_list", [])),
            "campaign_json": campaign_info,
        })
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            if "Kubernetes" in error_msg:
                state["production_url"] = f"local://production/{state['campaign_id']}"
                state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                                      "content": "Production ready (local mode)"}]
            else:
                state["error_message"] = error_msg
                state["status"] = "failed"
        else:
            state["production_url"] = result.get("production_url", "")
            state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                                  "content": f"Production deployed at {state['production_url']}"}]
    except Exception:
        state["production_url"] = f"local://production/{state['campaign_id']}"
        state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                              "content": "Production ready (local mode)"}]
    return state


async def send_emails_node(state: CampaignState) -> CampaignState:
    await publish_event(state["campaign_id"], "workflow_status", "Campaign Director",
                        "Sending to recipients...", {"step": "sending_emails"})
    customers = [CustomerProfile(**c) for c in state["customer_list"]]
    result = await call_a2a_agent(settings.DELIVERY_MANAGER_URL, "send_emails", {
        "campaign_id": state["campaign_id"],
        "customers": [c.model_dump() for c in customers],
        "email_subject_en": state["email_subject_en"],
        "email_body_en": state["email_body_en"],
        "email_subject_zh": state["email_subject_zh"],
        "email_body_zh": state["email_body_zh"],
        "campaign_url": state.get("production_url") or state.get("preview_url", ""),
    })
    if result.get("status") == "error":
        state["error_message"] = result.get("error", "Unknown error")
        state["status"] = "failed"
    else:
        state["status"] = "live"
        state["messages"] = [{"role": "assistant", "agent": "Delivery Manager",
                              "content": f"Sent {result.get('sent_count', 0)} emails (simulated)"}]
    return state


def _check_failed(state: CampaignState) -> str:
    return "end" if state.get("status") == "failed" else "continue"


def build_landing_page_workflow():
    workflow = StateGraph(CampaignState)
    workflow.add_node("generate_landing_page", generate_landing_page_node)
    workflow.add_node("deploy_preview", deploy_preview_node)
    workflow.add_edge(START, "generate_landing_page")
    workflow.add_conditional_edges("generate_landing_page", _check_failed, {"continue": "deploy_preview", "end": END})
    workflow.add_edge("deploy_preview", END)
    return workflow.compile()


def build_email_preview_workflow():
    workflow = StateGraph(CampaignState)
    workflow.add_node("retrieve_customers", retrieve_customers_node)
    workflow.add_node("generate_email", generate_email_node)
    workflow.add_edge(START, "retrieve_customers")
    workflow.add_conditional_edges("retrieve_customers", _check_failed, {"continue": "generate_email", "end": END})
    workflow.add_edge("generate_email", END)
    return workflow.compile()


def build_go_live_workflow():
    workflow = StateGraph(CampaignState)
    workflow.add_node("deploy_production", deploy_production_node)
    workflow.add_node("send_emails", send_emails_node)
    workflow.add_edge(START, "deploy_production")
    workflow.add_conditional_edges("deploy_production", _check_failed, {"continue": "send_emails", "end": END})
    workflow.add_edge("send_emails", END)
    return workflow.compile()


def _make_initial_state(campaign_id: str, campaign) -> CampaignState:
    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.campaign_name,
        "campaign_description": campaign.campaign_description,
        "hotel_name": campaign.hotel_name,
        "target_audience": campaign.target_audience,
        "theme": campaign.theme,
        "start_date": campaign.start_date,
        "end_date": campaign.end_date,
        "status": "generating",
        "landing_page_html": campaign.landing_page_html or "",
        "hero_image_url": campaign.hero_image_url or "",
        "preview_url": campaign.preview_url or "",
        "production_url": campaign.production_url or "",
        "email_subject_en": campaign.email_subject_en or "",
        "email_body_en": campaign.email_body_en or "",
        "email_subject_zh": campaign.email_subject_zh or "",
        "email_body_zh": campaign.email_body_zh or "",
        "customer_list": [c.model_dump() for c in campaign.customer_list] if campaign.customer_list else [],
        "customer_count": campaign.customer_count,
        "error_message": "",
        "messages": []
    }


def _get_username_from_auth() -> str:
    auth = _auth_header.get("")
    if not auth or not auth.startswith("Bearer "):
        return ""
    try:
        import base64
        payload = auth.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("preferred_username", "")
    except Exception:
        return ""


def _set_trace_attributes(campaign_id: str, workflow_name: str):
    mlflow_span = mlflow.get_current_active_span()
    if mlflow_span:
        otel_span = mlflow_span._span
        if otel_span.is_recording():
            otel_span.set_attribute("session.id", campaign_id)
            username = _get_username_from_auth()
            if username:
                otel_span.set_attribute("user.id", username)
            otel_span.set_attribute("mlflow.traceName", workflow_name)


@mlflow.trace(name="landing_page")
async def _run_landing_page_workflow(campaign_id: str, campaign):
    _set_trace_attributes(campaign_id, "landing_page")
    try:
        state = _make_initial_state(campaign_id, campaign)
        workflow = build_landing_page_workflow()
        final = await workflow.ainvoke(state)
        campaign.landing_page_html = final.get("landing_page_html", "")
        campaign.hero_image_url = final.get("hero_image_url", "") or None
        campaign.preview_url = final.get("preview_url", "")
        campaign.status = CampaignStatus(final.get("status", "preview_ready"))
        campaign.error_message = final.get("error_message")
    except Exception as e:
        traceback.print_exc()
        campaign.status = CampaignStatus.FAILED
        campaign.error_message = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
    campaigns_store.sync(campaign_id)


@mlflow.trace(name="email_preview")
async def _run_email_preview_workflow(campaign_id: str, campaign):
    _set_trace_attributes(campaign_id, "email_preview")
    try:
        state = _make_initial_state(campaign_id, campaign)
        state["status"] = campaign.status.value
        workflow = build_email_preview_workflow()
        final = await workflow.ainvoke(state)
        campaign.email_subject_en = final.get("email_subject_en", "")
        campaign.email_body_en = final.get("email_body_en", "")
        campaign.email_subject_zh = final.get("email_subject_zh", "")
        campaign.email_body_zh = final.get("email_body_zh", "")
        campaign.customer_list = [CustomerProfile(**c) for c in final.get("customer_list", [])]
        campaign.customer_count = final.get("customer_count", 0)
        campaign.status = CampaignStatus(final.get("status", "email_ready"))
        campaign.error_message = final.get("error_message")
    except Exception as e:
        traceback.print_exc()
        campaign.status = CampaignStatus.FAILED
        campaign.error_message = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
    campaigns_store.sync(campaign_id)


@mlflow.trace(name="go_live")
async def _run_go_live_workflow(campaign_id: str, campaign):
    _set_trace_attributes(campaign_id, "go_live")
    try:
        state = _make_initial_state(campaign_id, campaign)
        state["status"] = "approved"
        state["production_url"] = ""
        workflow = build_go_live_workflow()
        final = await workflow.ainvoke(state)
        campaign.production_url = final.get("production_url", "")
        campaign.status = CampaignStatus(final.get("status", "live"))
        campaign.error_message = final.get("error_message")
    except Exception as e:
        traceback.print_exc()
        campaign.status = CampaignStatus.FAILED
        campaign.error_message = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
    campaigns_store.sync(campaign_id)


class CampaignDirectorAgent:
    async def handle_skill(self, skill: str, params: dict) -> dict:
        if skill == "create_campaign":
            return await self._create_campaign(params)
        elif skill == "generate_landing_page":
            return await self._generate_landing_page(params)
        elif skill == "prepare_email_preview":
            return await self._prepare_email_preview(params)
        elif skill == "go_live":
            return await self._go_live(params)
        elif skill == "delete_campaign":
            return await self._delete_campaign(params)
        elif skill == "chat":
            return self._handle_chat(params)
        else:
            return {"error": f"Unknown skill: {skill}"}

    def _handle_chat(self, params: dict) -> dict:
        campaigns = list(campaigns_store.values())
        summary = f"{brand('director_intro', 'I am the Campaign Director.')} I orchestrate marketing campaign creation using AI agents.\n\n"
        if campaigns:
            summary += f"Currently managing {len(campaigns)} campaign(s):\n"
            for c in campaigns[-5:]:
                summary += f"- {c.campaign_name} ({c.status.value})\n"
        else:
            summary += "No active campaigns. Use the Campaign Wizard UI to create one.\n"
        summary += f"\nAvailable skills: create_campaign, generate_landing_page, prepare_email_preview, go_live"
        return {"response": summary}

    async def _create_campaign(self, params: dict) -> dict:
        req = CampaignRequest(**params)
        campaign_id = str(uuid.uuid4())[:8]
        campaign = CampaignData(
            id=campaign_id,
            campaign_name=req.campaign_name,
            campaign_description=req.campaign_description,
            hotel_name=req.hotel_name,
            target_audience=req.target_audience,
            theme=req.theme.value if hasattr(req.theme, 'value') else req.theme,
            start_date=req.start_date,
            end_date=req.end_date,
            status=CampaignStatus.DRAFT
        )
        campaigns_store[campaign_id] = campaign
        await publish_event(campaign_id, "campaign_created", "Campaign Director",
                            "Campaign created", {"campaign_id": campaign_id})
        return {"campaign_id": campaign_id, "status": "created"}

    async def _generate_landing_page(self, params: dict) -> dict:
        campaign_id = params.get("campaign_id")
        if not campaign_id or campaign_id not in campaigns_store:
            return {"error": "Campaign not found"}
        campaign = campaigns_store[campaign_id]
        if campaign.status == CampaignStatus.GENERATING:
            return {"campaign_id": campaign_id, "status": campaign.status.value}
        campaign.status = CampaignStatus.GENERATING
        asyncio.create_task(_run_landing_page_workflow(campaign_id, campaign))
        return {"campaign_id": campaign_id, "status": "generating"}

    async def _prepare_email_preview(self, params: dict) -> dict:
        campaign_id = params.get("campaign_id")
        if not campaign_id or campaign_id not in campaigns_store:
            return {"error": "Campaign not found"}
        campaign = campaigns_store[campaign_id]
        if campaign.status == CampaignStatus.PREPARING_EMAIL:
            return {"campaign_id": campaign_id, "status": campaign.status.value}
        campaign.status = CampaignStatus.PREPARING_EMAIL
        asyncio.create_task(_run_email_preview_workflow(campaign_id, campaign))
        return {"campaign_id": campaign_id, "status": "preparing_email"}

    async def _go_live(self, params: dict) -> dict:
        campaign_id = params.get("campaign_id")
        if not campaign_id or campaign_id not in campaigns_store:
            return {"error": "Campaign not found"}
        campaign = campaigns_store[campaign_id]
        if campaign.status == CampaignStatus.DEPLOYING:
            return {"campaign_id": campaign_id, "status": campaign.status.value}
        campaign.status = CampaignStatus.DEPLOYING
        asyncio.create_task(_run_go_live_workflow(campaign_id, campaign))
        return {"campaign_id": campaign_id, "status": "deploying"}

    async def _delete_campaign(self, params: dict) -> dict:
        campaign_id = params.get("campaign_id")
        if not campaign_id:
            return {"error": "campaign_id is required"}
        campaign = campaigns_store.pop(campaign_id, None)
        campaign_name = campaign.campaign_name if campaign else campaign_id[:8]
        asyncio.create_task(_cleanup_k8s_resources(campaign_id))
        await publish_event(campaign_id, "campaign_deleted", "Campaign Director",
                            f"Campaign '{campaign_name}' deleted")
        return {"campaign_id": campaign_id, "status": "deleted"}
