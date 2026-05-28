import json
import logging
from contextlib import nullcontext

import httpx
import mlflow
from mlflow.entities import SpanType
from openai import AsyncOpenAI

from app.schemas import CustomerProfile, GetTargetCustomersOutput
from app.settings import settings
from app.vertical_config import prompt as vcfg_prompt, seed_data

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_customers_by_tier",
            "description": "Retrieve VIP customers by membership tier (platinum, gold, diamond)",
            "parameters": {
                "type": "object",
                "properties": {
                    "tier": {"type": "string", "description": "Membership tier: platinum, gold, or diamond"},
                    "limit": {"type": "integer", "description": "Max customers to return", "default": 50}
                },
                "required": ["tier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_prospects",
            "description": "Retrieve prospect list — potential customers who are not yet members",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max prospects to return", "default": 50}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_high_spend_customers",
            "description": "Retrieve customers with total spend above a threshold (whales/VVIPs)",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_spend": {"type": "integer", "description": "Minimum total spend amount", "default": 500000},
                    "limit": {"type": "integer", "description": "Max customers to return", "default": 50}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_vip_customers",
            "description": "Retrieve all VIP customers regardless of tier",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max customers to return", "default": 100}
                }
            }
        }
    },
]

_system_prompt_cache = None


def _get_system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is not None:
        return _system_prompt_cache
    _system_prompt_cache = f"""{vcfg_prompt("customer_analyst_system", "You are a customer data analyst for a luxury casino resort. Given a target audience description, decide which database tool to call to retrieve the right customer segment.")} You have access to the following tools:

- get_customers_by_tier: For specific tier queries (platinum, gold, diamond members)
- get_prospects: For new/potential customers who aren't members yet
- get_high_spend_customers: For high-spending VIP/whale customers
- get_all_vip_customers: For broad targeting across all VIP tiers

Call exactly ONE tool based on the target audience description. Do not call multiple tools."""
    return _system_prompt_cache


_llm_client = AsyncOpenAI(
    base_url=settings.MODEL_ENDPOINT or "http://localhost:11434/v1",
    api_key=settings.MODEL_API_KEY or "unused",
    timeout=120.0,
    http_client=httpx.AsyncClient(verify=False),
)


def is_mock_mode() -> bool:
    return not settings.MODEL_ENDPOINT


async def publish_event(campaign_id: str, event_type: str, agent: str, task: str, data: dict = None):
    if not settings.EVENT_HUB_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.EVENT_HUB_URL}/events/{campaign_id}/publish",
                json={"event_type": event_type, "agent": agent, "task": task, "data": data or {}},
                timeout=5.0
            )
    except Exception as e:
        logger.warning("Failed to publish event: %s", e)


_seed_catalog = None


def _get_seed_catalog():
    global _seed_catalog
    if _seed_catalog is not None:
        return _seed_catalog
    _sd = seed_data()
    _seed_catalog = (_sd.get("customers", []), _sd.get("prospects", []))
    return _seed_catalog


async def fake_call_mcp_tool(tool_name: str, arguments: dict) -> list:
    customers, prospects = _get_seed_catalog()
    limit = int(arguments.get("limit", 50))

    if tool_name == "get_customers_by_tier":
        tier = (arguments.get("tier") or "").lower()
        return [c for c in customers if str(c.get("tier", "")).lower() == tier][:limit]
    if tool_name == "get_prospects":
        return prospects[:limit]
    if tool_name == "get_high_spend_customers":
        min_spend = int(arguments.get("min_spend", 500000))
        return [c for c in customers if int(c.get("total_spend", 0) or 0) >= min_spend][:limit]
    if tool_name == "get_all_vip_customers":
        return list(customers)[:limit]
    return []


async def call_mcp_tool(tool_name: str, arguments: dict, auth_headers: dict = None) -> list:
    from fastmcp import Client
    token = None
    if auth_headers:
        auth_value = auth_headers.get("Authorization", "")
        if auth_value.startswith("Bearer "):
            token = auth_value.removeprefix("Bearer ").strip()
    async with Client(f"{settings.MONGODB_MCP_URL}/mcp", auth=token) as mcp_client:
        result = await mcp_client.call_tool(tool_name, arguments)
        return json.loads(result.content[0].text) if result and result.content else []


def _keyword_select_tool(target_audience: str, limit: int) -> tuple[str, str]:
    audience_lower = target_audience.lower()
    if "new" in audience_lower or "prospect" in audience_lower:
        return "get_prospects", json.dumps({"limit": limit})
    elif "platinum" in audience_lower:
        return "get_customers_by_tier", json.dumps({"tier": "platinum", "limit": limit})
    elif "diamond" in audience_lower:
        return "get_customers_by_tier", json.dumps({"tier": "diamond", "limit": limit})
    elif "gold" in audience_lower:
        return "get_customers_by_tier", json.dumps({"tier": "gold", "limit": limit})
    elif "high" in audience_lower or "spend" in audience_lower or "whale" in audience_lower:
        return "get_high_spend_customers", json.dumps({"min_spend": 500000, "limit": limit})
    else:
        return "get_all_vip_customers", json.dumps({"limit": limit})


async def _llm_select_and_call_tool(user_prompt: str, target_audience: str = "", limit: int = 50, auth_headers: dict = None) -> tuple[list, str]:
    if is_mock_mode():
        tool_name, tool_args_str = _keyword_select_tool(target_audience or user_prompt, limit)
        arguments = json.loads(tool_args_str)
        result = await fake_call_mcp_tool(tool_name, arguments)
        recipient_type = "prospects" if tool_name == "get_prospects" else "customers"
        return result, recipient_type

    stream = await _llm_client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=[
            {"role": "system", "content": _get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.1,
        max_tokens=256,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    tool_call_name = None
    tool_call_args = ""

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.tool_calls:
            tc = chunk.choices[0].delta.tool_calls[0]
            if tc.function and tc.function.name:
                tool_call_name = tc.function.name
            if tc.function and tc.function.arguments:
                tool_call_args += tc.function.arguments

    if not tool_call_name:
        tool_call_name, tool_call_args = _keyword_select_tool(target_audience, limit)

    try:
        arguments = json.loads(tool_call_args) if tool_call_args else {}
    except json.JSONDecodeError:
        arguments = {}
    if "limit" not in arguments:
        arguments["limit"] = limit

    logger.info("LLM selected MCP tool=%s arguments=%s", tool_call_name, json.dumps(arguments, default=str))
    result = await call_mcp_tool(tool_call_name, arguments, auth_headers=auth_headers)
    recipient_type = "prospects" if tool_call_name == "get_prospects" else "customers"
    return result, recipient_type


def _restore_trace_context(headers):
    if headers and "traceparent" in headers:
        from mlflow.tracing import set_tracing_context_from_http_request_headers
        return set_tracing_context_from_http_request_headers(headers)
    return nullcontext()


class CustomerAnalystAgent:
    def __init__(self):
        self.headers = {}

    async def get_customers(self, params: dict, agent_headers: dict = None) -> dict:
        user_prompt = params.get("user_prompt")
        campaign_id = params.get("campaign_id", "unknown")
        limit = params.get("limit", 50)
        target_audience = params.get("target_audience", "all VIP")

        await publish_event(campaign_id, "agent_started", "Customer Analyst", f"Identifying {target_audience}...")

        try:
            with _restore_trace_context(agent_headers):
                with mlflow.start_span("customer_analyst", span_type=SpanType.AGENT) as span:
                    span._span.set_attribute("session.id", campaign_id)
                    span.set_inputs({"target_audience": target_audience, "limit": limit, "campaign_id": campaign_id})

                    await publish_event(campaign_id, "workflow_status", "Customer Analyst", "Analyzing target audience...")

                    if user_prompt:
                        customers_data, recipient_type = await _llm_select_and_call_tool(user_prompt, limit=limit, auth_headers=self.headers)
                    else:
                        prompt = f"Retrieve customers for this target audience: {target_audience} (limit: {limit})"
                        customers_data, recipient_type = await _llm_select_and_call_tool(prompt, target_audience, limit, auth_headers=self.headers)

                    customers = [
                        CustomerProfile(
                            customer_id=c.get("customer_id", ""),
                            name=c.get("name", ""),
                            name_en=c.get("name_en"),
                            email=c.get("email", ""),
                            tier=c.get("tier", ""),
                            preferred_language=c.get("preferred_language", "en"),
                            interests=c.get("interests", []),
                            total_spend=c.get("total_spend"),
                            last_visit=c.get("last_visit"),
                            source=c.get("source")
                        )
                        for c in customers_data
                    ]

                    await publish_event(campaign_id, "agent_completed", "Customer Analyst",
                                      f"Found {len(customers)} {recipient_type}",
                                      {"count": len(customers), "recipient_type": recipient_type})

                    result = GetTargetCustomersOutput(
                        customers=customers, count=len(customers),
                        recipient_type=recipient_type, status="success"
                    ).model_dump()
                    span.set_outputs({"count": len(customers), "recipient_type": recipient_type, "status": "success"})
                    return result

        except Exception as e:
            logger.exception("get_customers failed")
            await publish_event(campaign_id, "agent_error", "Customer Analyst",
                              "Could not retrieve customers", {"error": str(e)})
            return GetTargetCustomersOutput(
                customers=[], count=0, recipient_type="unknown",
                status="error", error=str(e)
            ).model_dump()
