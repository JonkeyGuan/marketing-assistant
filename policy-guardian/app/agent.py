import json
import httpx
from contextlib import nullcontext
from openai import AsyncOpenAI
import mlflow
from mlflow.entities import SpanType
from app.settings import settings
from app.vertical_config import prompt as vcfg_prompt

_policy_prompt_cache = None


def _get_policy_prompt() -> str:
    global _policy_prompt_cache
    if _policy_prompt_cache is not None:
        return _policy_prompt_cache
    pg_intro = vcfg_prompt("policy_guardian_intro", "You are a luxury casino resort marketing policy validator.")
    pg_rejected = vcfg_prompt("policy_guardian_rejected_examples", '- "99% Off All Hotel Rooms" → REJECTED: Unrealistic discount\n- "Free Everything For Everyone" → REJECTED: Unrealistic offer\n- "Win Big Guaranteed at Our Tables" → REJECTED: Misleading promise\n- "Cheapest Rooms in Macau" → REJECTED: Not appropriate for luxury brand')
    pg_approved = vcfg_prompt("policy_guardian_approved_examples", '- "Exclusive 30% off suites for platinum members" → APPROVED\n- "Complimentary spa treatment with 2-night stay" → APPROVED\n- "Private dining experience for diamond tier guests" → APPROVED\n- "VIP gala evening with world-class entertainment" → APPROVED')
    pg_cost = vcfg_prompt("policy_guardian_cost_note", "a luxury hotel night costs $300+")
    _policy_prompt_cache = f"""{pg_intro}

RULES:
1. No discounts greater than 50%
2. Must be professional and appropriate for a premium brand
3. No unrealistic or misleading promises
4. No references to gambling addiction or irresponsible behavior
5. Must maintain exclusivity — no cheap or mass-market language

EXAMPLES OF REJECTED CAMPAIGNS:
{pg_rejected}
- "Buy 2 Nights Get 80% Off" → REJECTED: Unrealistic discount
- "Unlimited Free Drinks and Casino Credits" → REJECTED: Unrealistic offer

EXAMPLES OF APPROVED CAMPAIGNS:
{pg_approved}
- "50% off luxury suite upgrade for loyalty members" → APPROVED
- "Free 2 night stay with $1000 spent" → APPROVED (conditional offer, not unrealistic)
- "Complimentary airport transfer for VIP members" → APPROVED
- "Earn a free night for every 3 nights booked" → APPROVED (loyalty reward)

NOTE: "Free" or "complimentary" offers are only APPROVED if the condition is proportional to the reward. Examples:
- "Free 2 nights with $1000 spent" → APPROVED (proportional)
- "Free 2 nights with $50 spent" → REJECTED (spend too low for the reward)
- "Free spa with 2-night booking" → APPROVED (proportional)
Use common sense: {pg_cost}. The spend must be reasonable relative to what is offered for free.

NOW EVALUATE:
Campaign Name: {{campaign_name}}
Campaign Description: {{description}}

Respond with ONLY: APPROVED or REJECTED: <brief reason>
No thinking, no XML tags, one line only."""
    return _policy_prompt_cache


async def publish_event(campaign_id: str, event_type: str, agent: str, task: str, data: dict = None):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.EVENT_HUB_URL}/events/{campaign_id}/publish",
                json={"event_type": event_type, "agent": agent, "task": task, "data": data or {}},
                timeout=5.0
            )
    except Exception as e:
        print(f"[Policy Guardian] Failed to publish event: {e}")


_llm_client = AsyncOpenAI(
    base_url=settings.MODEL_ENDPOINT or "http://localhost:11434/v1",
    api_key=settings.MODEL_API_KEY or "unused",
    timeout=30.0,
    http_client=httpx.AsyncClient(verify=False),
)


def is_mock_mode() -> bool:
    return not settings.MODEL_ENDPOINT


async def validate_policy(campaign_name: str, description: str) -> dict:
    if is_mock_mode():
        print("[Policy Guardian] Mock mode — auto-approving")
        return {"approved": True, "reason": ""}

    prompt = _get_policy_prompt().format(campaign_name=campaign_name, description=description)
    try:
        response = await _llm_client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        answer = response.choices[0].message.content.strip()
        if "</think>" in answer:
            answer = answer.split("</think>")[-1].strip()
        if answer.upper().startswith("REJECTED"):
            reason = answer.split(":", 1)[1].strip() if ":" in answer else "Campaign policy violation"
            return {"approved": False, "reason": reason}
        return {"approved": True, "reason": ""}
    except Exception as e:
        print(f"[Policy Guardian] LLM error: {e}")
        return {"approved": True, "reason": ""}


def _restore_trace_context(headers):
    if headers and "traceparent" in headers:
        from mlflow.tracing import set_tracing_context_from_http_request_headers
        return set_tracing_context_from_http_request_headers(headers)
    return nullcontext()


class PolicyGuardianAgent:
    async def validate(self, params: dict, agent_headers: dict = None) -> dict:
        campaign_id = params.get("campaign_id", "unknown")
        campaign_name = params.get("campaign_name", "")
        description = params.get("campaign_description", "")

        await publish_event(campaign_id, "agent_started", "Policy Guardian", "Checking campaign policies...")

        try:
            with _restore_trace_context(agent_headers):
                with mlflow.start_span("policy_guardian", span_type=SpanType.AGENT) as span:
                    span._span.set_attribute("session.id", campaign_id)
                    span.set_inputs({"campaign_name": campaign_name, "description": description})

                    result = await validate_policy(campaign_name, description)
                    if result["approved"]:
                        await publish_event(campaign_id, "agent_completed", "Policy Guardian", "Campaign approved")
                        output = {"approved": True, "reason": "", "status": "success"}
                    else:
                        await publish_event(campaign_id, "agent_completed", "Policy Guardian", f"Campaign rejected: {result['reason']}")
                        output = {"approved": False, "reason": result["reason"], "status": "success"}
                    span.set_outputs(output)
                    return output
        except Exception as e:
            await publish_event(campaign_id, "agent_error", "Policy Guardian", "Policy check failed", {"error": str(e)})
            return {"approved": True, "reason": "", "status": "error", "error": str(e)}
