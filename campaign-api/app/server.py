import re
import uuid
import json
import asyncio
import httpx
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

from app.settings import settings
from app.schemas import CampaignRequest, CampaignTheme, CAMPAIGN_THEMES
from app.vertical_config import competitors as vcfg_competitors, brand, get_config, seed_data as vcfg_seed

app = Flask(__name__)
CORS(app)


def _build_competitor_pattern() -> str:
    names = vcfg_competitors()
    if names:
        escaped = [re.escape(name) for name in names]
        return r"(?i)(" + "|".join(escaped) + ")"
    return r"(?i)(jennifer casino|jennifer resort|lucky star casino|jade emperor palace|phoenix bay resort|emerald fortune club|royal lotus gaming)"

COMPETITOR_PATTERN = _build_competitor_pattern()


def guardrail_failure(layer_id: str, layer_name: str, title: str, reason: str, guidance: str, details: dict | None = None) -> dict:
    return {
        "passed": False,
        "layer": {"id": layer_id, "name": layer_name},
        "title": title,
        "reason": reason,
        "guidance": guidance,
        "details": details or {},
    }


def check_guardrails(campaign_name: str, description: str) -> dict:
    text = f"{campaign_name} {description}"

    match = re.search(COMPETITOR_PATTERN, text)
    if match:
        blocked_term = match.group(0)
        return guardrail_failure(
            "regex_competitor", "Brand Compliance",
            "Competitor reference detected",
            f'The campaign mentions "{blocked_term}", which is blocked by the competitor-name guardrail.',
            "Remove competitor brand names and rewrite the campaign using your own property names only.",
            {"matched_text": blocked_term},
        )

    try:
        from a2a.client import create_client, ClientConfig
        from a2a.types import SendMessageRequest, Message, Part, Role

        async def _call_policy():
            req = SendMessageRequest(
                message=Message(
                    role=Role.ROLE_USER,
                    message_id=uuid.uuid4().hex,
                    parts=[Part(text=json.dumps({
                        "skill": "validate_campaign",
                        "campaign_name": campaign_name,
                        "campaign_description": description,
                    }))],
                ),
            )
            timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
            config = ClientConfig(httpx_client=httpx.AsyncClient(timeout=timeout))
            client = await create_client(settings.POLICY_GUARDIAN_URL, client_config=config)
            try:
                last_task = None
                artifacts = []
                async for event in client.send_message(req):
                    if event.HasField("task"):
                        last_task = event.task
                    elif event.HasField("artifact_update"):
                        artifacts.append(event.artifact_update.artifact)
                all_artifacts = list(last_task.artifacts) if last_task and last_task.artifacts else artifacts
                if all_artifacts:
                    text = all_artifacts[0].parts[0].text
                    return json.loads(text)
            finally:
                await client.close()
            return {"approved": True}

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_call_policy())
        finally:
            loop.close()

        if result.get("approved") is False:
            reason = result.get("reason", "Campaign does not meet policy requirements.")
            return guardrail_failure(
                "policy_guardian", "Campaign Policy Review",
                "Business policy violation", reason,
                "Adjust the offer so it stays realistic, premium, and compliant with campaign policy.",
                {"policy_reason": reason},
            )
    except Exception as e:
        print(f"[Guardrails] Policy Guardian check failed (non-blocking): {e}")

    return {"passed": True, "layer": None, "title": "", "reason": "", "guidance": "", "details": {}}


def _check_role_audience_restriction(target_audience: str, auth_header: str) -> dict | None:
    import base64 as _b64
    if not re.search(r"platinum", target_audience, re.IGNORECASE):
        return None
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        token = auth_header.split(" ", 1)[1]
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(_b64.urlsafe_b64decode(payload_b64))
        roles = payload.get("realm_access", {}).get("roles", [])
        if "platinum-access" in roles:
            return None
        return guardrail_failure(
            "role_restriction", "Access Restriction",
            "Insufficient permissions for Platinum tier",
            "Your role does not permit targeting Platinum-tier members.",
            "Select a different target audience or contact your administrator for elevated access.",
        )
    except Exception:
        return None


def call_director_a2a_sync(skill: str, params: dict, auth_header: str = "") -> dict:
    from a2a.client import create_client, ClientConfig
    from a2a.types import SendMessageRequest, Message, Part, Role

    async def _call():
        req = SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                message_id=uuid.uuid4().hex,
                parts=[Part(text=json.dumps({"skill": skill, **params}))],
            ),
        )
        timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        config = ClientConfig(httpx_client=httpx.AsyncClient(timeout=timeout, headers=headers))
        client = await create_client(settings.CAMPAIGN_DIRECTOR_URL, client_config=config)
        try:
            last_task = None
            artifacts = []
            async for event in client.send_message(req):
                if event.HasField("task"):
                    last_task = event.task
                elif event.HasField("artifact_update"):
                    artifacts.append(event.artifact_update.artifact)
            all_artifacts = list(last_task.artifacts) if last_task and last_task.artifacts else artifacts
            for artifact in all_artifacts:
                for part in artifact.parts:
                    if part.text:
                        try:
                            return json.loads(part.text)
                        except json.JSONDecodeError:
                            return {"status": "success", "content": part.text}
        finally:
            await client.close()
        return {"error": "No artifact returned from Campaign Director"}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_call())
    finally:
        loop.close()


@app.route("/healthz", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "Campaign API"})

@app.route("/readyz")
def readiness_check():
    return health_check()


@app.route("/api/themes", methods=["GET"])
def get_themes():
    return jsonify(CAMPAIGN_THEMES)


@app.route("/api/config", methods=["GET"])
def get_vertical_config():
    cfg = get_config()
    return jsonify({
        "brand": cfg.get("brand", {}),
        "properties": cfg.get("properties", []),
        "property_label": cfg.get("property_label", "Property"),
        "tiers": cfg.get("tiers", {}),
        "audience_suggestions": cfg.get("audience_suggestions", []),
        "themes": cfg.get("themes", {}),
        "quick_start_presets": cfg.get("quick_start_presets", []),
        "guardrail_presets": cfg.get("guardrail_presets", []),
        "competitors": cfg.get("competitors", []),
        "default_inbox_email": cfg.get("seed_data", {}).get("default_inbox_email", ""),
    })


@app.route("/api/campaigns", methods=["GET"])
def list_campaigns():
    try:
        auth_header = request.headers.get("Authorization", "")
        headers = {"Authorization": auth_header} if auth_header else {}
        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.get(f"{settings.CAMPAIGN_DIRECTOR_URL}/campaigns")
            if response.status_code != 200:
                return jsonify({"error": "Failed to fetch campaigns"}), 500
            return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<campaign_id>", methods=["GET"])
def get_campaign(campaign_id: str):
    try:
        auth_header = request.headers.get("Authorization", "")
        headers = {"Authorization": auth_header} if auth_header else {}
        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.get(f"{settings.CAMPAIGN_DIRECTOR_URL}/campaigns/{campaign_id}")
            if response.status_code == 404:
                return jsonify({"error": "Campaign not found"}), 404
            return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/validate", methods=["POST"])
def validate_campaign():
    try:
        data = request.get_json()
        auth_header = request.headers.get("Authorization", "")
        role_check = _check_role_audience_restriction(data.get("target_audience", ""), auth_header)
        if role_check:
            return jsonify({"valid": False, "reason": role_check["reason"], "guardrail": role_check}), 200
        name = data.get("campaign_name", "")
        desc = data.get("campaign_description", "")
        result = check_guardrails(name, desc)
        if not result["passed"]:
            return jsonify({"valid": False, "reason": result["reason"], "guardrail": result}), 200
        return jsonify({"valid": True, "reason": "", "guardrail": result}), 200
    except Exception:
        return jsonify({"valid": True, "reason": ""}), 200


@app.route("/api/campaigns", methods=["POST"])
def create_campaign():
    try:
        data = request.get_json()
        auth_header = request.headers.get("Authorization", "")
        role_check = _check_role_audience_restriction(data.get("target_audience", ""), auth_header)
        if role_check:
            return jsonify({"error": role_check["reason"], "guardrail_blocked": True, "guardrail": role_check}), 403
        guardrails = check_guardrails(data.get("campaign_name", ""), data.get("campaign_description", ""))
        if not guardrails["passed"]:
            return jsonify({"error": guardrails["reason"], "guardrail_blocked": True, "guardrail": guardrails}), 400
        result = call_director_a2a_sync("create_campaign", data, auth_header)
        if "error" in result and result["error"]:
            return jsonify(result), 500
        return jsonify(result), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<campaign_id>/generate", methods=["POST"])
def generate_landing_page(campaign_id: str):
    try:
        auth_header = request.headers.get("Authorization", "")
        result = call_director_a2a_sync("generate_landing_page", {"campaign_id": campaign_id}, auth_header)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<campaign_id>/preview-email", methods=["POST"])
def preview_email(campaign_id: str):
    try:
        auth_header = request.headers.get("Authorization", "")
        result = call_director_a2a_sync("prepare_email_preview", {"campaign_id": campaign_id}, auth_header)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<campaign_id>/approve", methods=["POST"])
def approve_campaign(campaign_id: str):
    try:
        auth_header = request.headers.get("Authorization", "")
        result = call_director_a2a_sync("go_live", {"campaign_id": campaign_id}, auth_header)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<campaign_id>", methods=["DELETE"])
def delete_campaign(campaign_id: str):
    try:
        auth_header = request.headers.get("Authorization", "")
        result = call_director_a2a_sync("delete_campaign", {"campaign_id": campaign_id}, auth_header)
        if "error" in result and result["error"]:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


INBOX_TEMPLATES = [
    {
        "from_name": "Simon Casino Resort",
        "from_email": "vip@simoncasino.com",
        "subject": "Your {tier} Membership Has Been Renewed",
        "body": "<p>Dear {name},</p><p>We are pleased to confirm that your {tier} membership has been successfully renewed for another year.</p><p>As a valued member, you continue to enjoy exclusive benefits including priority reservations, complimentary spa access, and dedicated concierge service.</p><p>Best regards,<br>Simon Casino Resort VIP Services</p>",
        "date": "2026-03-15T10:30:00",
    },
    {
        "from_name": "Simon Casino Resort",
        "from_email": "dining@simoncasino.com",
        "subject": "Exclusive Wine Tasting Event — March 28",
        "body": "<p>Dear {name},</p><p>You are cordially invited to an exclusive wine tasting event featuring rare vintages from our award-winning cellar.</p><p><strong>Date:</strong> March 28, 2026<br><strong>Time:</strong> 7:00 PM<br><strong>Venue:</strong> The Grand Cellar, Level B1</p><p>Limited to 20 guests. Please RSVP at your earliest convenience.</p><p>Warm regards,<br>The Dining Team</p>",
        "date": "2026-03-20T14:15:00",
    },
    {
        "from_name": "Simon Casino Resort",
        "from_email": "concierge@simoncasino.com",
        "subject": "Your Suite Upgrade Confirmation",
        "body": "<p>Dear {name},</p><p>Great news! Your upcoming stay has been upgraded to the Presidential Suite as a token of our appreciation for your loyalty.</p><p><strong>Check-in:</strong> April 5, 2026<br><strong>Suite:</strong> Presidential Suite, Floor 38<br><strong>Amenities:</strong> Private butler, panoramic city view, complimentary minibar</p><p>We look forward to welcoming you.</p><p>Best regards,<br>Concierge Team</p>",
        "date": "2026-03-25T09:00:00",
    },
]

CAMPAIGN_EMAILS = []


def get_inbox_for(email_filter=None):
    all_emails = []
    _seed = vcfg_seed()
    _customers = _seed.get("customers", [])
    known_customers = [
        {"name": c.get("name_en", c.get("name", "")), "email": c.get("email", ""), "tier": c.get("tier", "").title()}
        for c in _customers[:5]
    ] if _customers else [
        {"name": "Wei Zhang", "email": "wei.zhang@example.com", "tier": "Platinum"},
    ]

    for cust in known_customers:
        if email_filter and cust["email"] != email_filter:
            continue
        for i, tmpl in enumerate(INBOX_TEMPLATES):
            all_emails.append({
                "id": f"inbox-{cust['email']}-{i}",
                "from_name": tmpl["from_name"],
                "from_email": tmpl["from_email"],
                "to_name": cust["name"],
                "to_email": cust["email"],
                "subject": tmpl["subject"].format(name=cust["name"], tier=cust["tier"]),
                "body": tmpl["body"].format(name=cust["name"], tier=cust["tier"]),
                "date": tmpl["date"],
                "read": True,
            })

    for ce in CAMPAIGN_EMAILS:
        if email_filter and ce.get("to_email") != email_filter:
            continue
        all_emails.append(ce)

    all_emails.sort(key=lambda e: (e.get("read", True), e.get("date", "")), reverse=False)
    unread = [e for e in all_emails if not e.get("read")]
    read = [e for e in all_emails if e.get("read")]
    read.sort(key=lambda e: e.get("date", ""), reverse=True)
    return unread + read


@app.route("/api/inbox", methods=["GET"])
def get_inbox():
    email_filter = request.args.get("email")
    return jsonify(get_inbox_for(email_filter))


@app.route("/api/inbox", methods=["POST"])
def add_to_inbox():
    email = request.get_json()
    email["id"] = f"inbox-{uuid.uuid4().hex[:6]}"
    email["read"] = False
    CAMPAIGN_EMAILS.append(email)
    return jsonify(email), 201


@app.route("/api/inbox/<email_id>/read", methods=["POST"])
def mark_read(email_id):
    for email in CAMPAIGN_EMAILS:
        if email["id"] == email_id:
            email["read"] = True
            return jsonify(email)
    return jsonify({"read": True}), 200


@app.route("/events/<campaign_id>", methods=["GET"])
def proxy_sse(campaign_id: str):
    def generate():
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=600.0, write=10.0, pool=10.0)) as client:
                with client.stream("GET", f"{settings.EVENT_HUB_URL}/events/{campaign_id}") as response:
                    for line in response.iter_lines():
                        yield line + "\n"
        except Exception:
            yield "data: {\"event_type\": \"error\", \"task\": \"SSE proxy disconnected\"}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
