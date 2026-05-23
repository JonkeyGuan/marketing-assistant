import json
import uuid
import datetime
import httpx
from typing import List
from openai import AsyncOpenAI

from app.settings import settings
from app.config_client import prompt as vcfg_prompt, brand
from app.models import (
    CustomerProfile,
    GenerateEmailInput, GenerateEmailOutput,
    DeployPreviewInput, DeployPreviewOutput,
    DeployProductionInput, DeployProductionOutput,
    SendEmailsInput, SendEmailsOutput,
)

_llm_client = AsyncOpenAI(
    base_url=settings.MODEL_ENDPOINT or "http://localhost:11434/v1",
    api_key=settings.MODEL_API_KEY or "unused",
    timeout=180.0,
    http_client=httpx.AsyncClient(verify=False),
)


def is_mock_mode() -> bool:
    return not settings.MODEL_ENDPOINT


MARKETING_SYSTEM_PROMPT = f"""{vcfg_prompt("delivery_manager_system", "You are a luxury casino marketing expert creating personalized email campaigns.")}

Generate email content in the following EXACT format:

---ENGLISH_SUBJECT---
[English email subject line here]

---ENGLISH_BODY---
[English email body as HTML fragment]

---CHINESE_SUBJECT---
[Chinese email subject line here]

---CHINESE_BODY---
[Chinese email body as HTML fragment]

## Email Body HTML Formatting Rules:
- Use ONLY inline HTML tags like <p>, <strong>, <em>, <a>, <br>
- Do NOT use <h1> or <h2> tags in the email body
- Do NOT include <!DOCTYPE>, <html>, <head>, <body>, or <style> tags
- Start with: <p>Dear {{{{customer_name}}}},</p> (greeting MUST be its own <p> tag)
- Wrap each paragraph in its own <p> tag for proper spacing
- For the CTA button, use: <p><a href="{{{{campaign_link}}}}" style="background-color:#C41E3A;color:#ffffff;padding:12px 24px;text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">Button Text</a></p>

## Email Style Guidelines:
- Keep subject lines under 60 characters
- Use elegant, premium language
- Use EXACTLY `{{{{customer_name}}}}` as the greeting placeholder
- The CTA button href MUST be EXACTLY `{{{{campaign_link}}}}`
- Sign off with the hotel/casino name"""


MOCK_EMAIL = {
    "email_subject_en": "An Exclusive Invitation Awaits You",
    "email_body_en": '<p>Dear {{customer_name}},</p><p>We are delighted to extend a most exclusive invitation to you. As one of our most valued guests, you have been selected to experience an extraordinary journey of luxury and indulgence.</p><p>Your personalized experience awaits — a page crafted exclusively for you.</p><p><a href="{{campaign_link}}" style="background-color:#C41E3A;color:#ffffff;padding:12px 24px;text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">Discover Your Invitation</a></p><p>With warmest regards,<br>Simon Casino Resort</p>',
    "email_subject_zh": "专属邀请函已为您准备",
    "email_body_zh": '<p>尊敬的 {{customer_name}},</p><p>我们非常荣幸地向您发出这份专属邀请。作为我们最尊贵的宾客之一，您已被选中体验一段非凡的奢华旅程。</p><p>您的专属体验已准备就绪 — 一个专为您打造的页面。</p><p><a href="{{campaign_link}}" style="background-color:#C41E3A;color:#ffffff;padding:12px 24px;text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">探索您的邀请</a></p><p>此致敬礼,<br>Simon Casino Resort</p>',
}


async def publish_event(campaign_id: str, event_type: str, agent: str, task: str, data: dict = None):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.EVENT_HUB_URL}/events/{campaign_id}/publish",
                json={"event_type": event_type, "agent": agent, "task": task, "data": data or {}},
                timeout=5.0
            )
    except Exception as e:
        print(f"[Delivery Manager] Failed to publish event: {e}")


def parse_email_response(response: str) -> dict:
    result = {
        "email_subject_en": "", "email_body_en": "",
        "email_subject_zh": "", "email_body_zh": "",
    }
    sections = {
        "---ENGLISH_SUBJECT---": "email_subject_en",
        "---ENGLISH_BODY---": "email_body_en",
        "---CHINESE_SUBJECT---": "email_subject_zh",
        "---CHINESE_BODY---": "email_body_zh",
    }
    current_section = None
    current_content = []

    for line in response.split("\n"):
        line_stripped = line.strip()
        if line_stripped in sections:
            if current_section:
                result[current_section] = "\n".join(current_content).strip()
            current_section = sections[line_stripped]
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        result[current_section] = "\n".join(current_content).strip()
    return result


async def generate_email_with_streaming(
    campaign_name: str, campaign_description: str, hotel_name: str,
    campaign_url: str, target_audience: str, start_date: str, end_date: str,
) -> dict:
    if is_mock_mode():
        print("[Delivery Manager] Mock mode — returning pre-canned emails")
        return dict(MOCK_EMAIL)

    date_info = ""
    if start_date and end_date:
        date_info = f"\n- **Campaign Period:** {start_date} to {end_date}"

    user_prompt = f"""Create a marketing email for the following campaign:

## Campaign Details:
- **Campaign Name:** {campaign_name}
- **Description:** {campaign_description}
- **Hotel/Casino:** {hotel_name}
- **Campaign Landing Page URL:** {campaign_url}
- **Target Audience:** {target_audience}{date_info}

## Requirements:
1. Create an enticing subject line
2. Write an elegant email body with personalized greeting using {{{{customer_name}}}}
3. CTA button href MUST be {{{{campaign_link}}}}
4. Include campaign dates ({start_date} to {end_date})
5. Provide both English and Chinese versions

Generate the email content now:"""

    stream = await _llm_client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=[
            {"role": "system", "content": MARKETING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4000,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    content = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content

    return parse_email_response(content)


def deploy_campaign_local(campaign_id: str, namespace: str) -> str:
    return f"local://{namespace}/campaign-{campaign_id[:8]}"


def _extract_hero_image_url(html: str, imagegen_base: str) -> tuple[str, str]:
    """Extract the hero image path from HTML and replace with /hero-image.png.
    Returns (modified_html, full_image_url). If no match, returns (html, "")."""
    import re
    match = re.search(r"url\(['\"]?(/images/[^'\")\s]+)['\"]?\)", html)
    if match:
        image_path = match.group(1)
        return html.replace(image_path, "/hero-image.png"), f"{imagegen_base}{image_path}"
    return html, ""


_SA_TOKEN_PATH = "/var/run/secrets/sa-token"


def _load_sa_token_fallback() -> bool:
    """Load K8s config from a mounted SA token Secret (fallback for broken projected volumes)."""
    import os
    from kubernetes import client
    token_file = os.path.join(_SA_TOKEN_PATH, "token")
    ca_file = os.path.join(_SA_TOKEN_PATH, "ca.crt")
    if not os.path.isfile(token_file):
        return False
    try:
        with open(token_file) as f:
            token = f.read().strip()
        configuration = client.Configuration()
        configuration.host = "https://kubernetes.default.svc"
        configuration.api_key = {"authorization": f"Bearer {token}"}
        configuration.api_key_prefix = {"authorization": ""}
        if os.path.isfile(ca_file):
            configuration.ssl_ca_cert = ca_file
        else:
            configuration.verify_ssl = False
        client.Configuration.set_default(configuration)
        print("[Delivery Manager] Using SA token fallback for K8s access")
        return True
    except Exception as e:
        print(f"[Delivery Manager] SA token fallback failed: {e}")
        return False


def deploy_campaign_to_k8s(campaign_id: str, html_content: str, namespace: str,
                           customers_json: str = "[]", campaign_json: str = "{}",
                           is_preview: bool = True) -> str:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    try:
        config.load_incluster_config()
    except config.ConfigException:
        try:
            config.load_kube_config()
        except config.ConfigException:
            if not _load_sa_token_fallback():
                print("[Delivery Manager] No K8s config — using local URL")
                return deploy_campaign_local(campaign_id, namespace)

    imagegen_base = f"http://imagegen-mcp.{settings.APP_NAMESPACE}.svc:8083"
    html_content, hero_image_url = _extract_hero_image_url(html_content, imagegen_base)

    core_v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    suffix = "preview" if is_preview else "live"
    deployment_name = f"campaign-{campaign_id[:8]}-{suffix}"

    data_configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=f"{deployment_name}-data"),
        data={
            "template.html": html_content,
            "customers.json": customers_json,
            "campaign.json": campaign_json,
        },
    )

    try:
        core_v1.create_namespaced_config_map(namespace=namespace, body=data_configmap)
    except ApiException as e:
        if e.status == 409:
            core_v1.replace_namespaced_config_map(
                name=f"{deployment_name}-data", namespace=namespace, body=data_configmap)
        else:
            raise

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": deployment_name}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": deployment_name}),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="landing",
                            image=settings.LANDING_IMAGE,
                            image_pull_policy="Always",
                            ports=[client.V1ContainerPort(container_port=3001)],
                            env=[
                                client.V1EnvVar(name="MONGODB_MCP_URL",
                                                value=f"http://mongodb-mcp.{settings.APP_NAMESPACE}.svc:8082"),
                                client.V1EnvVar(name="HERO_IMAGE_URL", value=hero_image_url),
                            ],
                            volume_mounts=[client.V1VolumeMount(name="data", mount_path="/data")],
                        )
                    ],
                    volumes=[client.V1Volume(
                        name="data",
                        config_map=client.V1ConfigMapVolumeSource(name=f"{deployment_name}-data"),
                    )],
                ),
            ),
        ),
    )

    try:
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
    except ApiException as e:
        if e.status == 409:
            apps_v1.replace_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        else:
            raise

    service = client.V1Service(
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=client.V1ServiceSpec(
            selector={"app": deployment_name},
            ports=[client.V1ServicePort(port=80, target_port=3001)],
        ),
    )

    try:
        core_v1.create_namespaced_service(namespace=namespace, body=service)
    except ApiException as e:
        if e.status != 409:
            raise

    route_url = f"https://{deployment_name}-{namespace}.{settings.CLUSTER_DOMAIN}/"

    try:
        custom_api = client.CustomObjectsApi()
        route = {
            "apiVersion": "route.openshift.io/v1",
            "kind": "Route",
            "metadata": {"name": deployment_name},
            "spec": {
                "to": {"kind": "Service", "name": deployment_name},
                "port": {"targetPort": 3001},
                "tls": {"termination": "edge"},
            },
        }
        try:
            custom_api.create_namespaced_custom_object(
                group="route.openshift.io", version="v1",
                namespace=namespace, plural="routes", body=route)
        except ApiException as e:
            if e.status != 409:
                raise
    except Exception as e:
        print(f"[Delivery Manager] Route creation failed (may not be OpenShift): {e}")

    return route_url


def cleanup_campaign_k8s(campaign_id: str):
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    try:
        config.load_incluster_config()
    except config.ConfigException:
        try:
            config.load_kube_config()
        except config.ConfigException:
            if not _load_sa_token_fallback():
                print(f"[Delivery Manager] No K8s config — skipping cleanup for {campaign_id}")
                return {"status": "skipped", "reason": "no k8s config"}

    core_v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    custom_api = client.CustomObjectsApi()
    short_id = campaign_id[:8]
    deleted = []

    for namespace in [settings.DEV_NAMESPACE, settings.PROD_NAMESPACE]:
        for suffix in ["preview", "live"]:
            name = f"campaign-{short_id}-{suffix}"
            for resource, delete_fn in [
                ("Deployment", lambda n=name, ns=namespace: apps_v1.delete_namespaced_deployment(n, ns)),
                ("Service", lambda n=name, ns=namespace: core_v1.delete_namespaced_service(n, ns)),
                ("ConfigMap", lambda n=name, ns=namespace: core_v1.delete_namespaced_config_map(f"{n}-data", ns)),
            ]:
                try:
                    delete_fn()
                    deleted.append(f"{resource}/{name} in {namespace}")
                except ApiException as e:
                    if e.status != 404:
                        print(f"[Delivery Manager] Failed to delete {resource} {name} in {namespace}: {e.reason}")
            try:
                custom_api.delete_namespaced_custom_object(
                    group="route.openshift.io", version="v1",
                    namespace=namespace, plural="routes", name=name)
                deleted.append(f"Route/{name} in {namespace}")
            except Exception:
                pass

    print(f"[Delivery Manager] Cleaned up: {deleted}")
    return {"status": "success", "deleted": deleted}


class DeliveryManagerAgent:
    async def generate_email(self, params: dict) -> dict:
        validated = GenerateEmailInput(**params)
        campaign_id = params.get("campaign_id", str(uuid.uuid4())[:8])

        await publish_event(campaign_id, "agent_started", "Delivery Manager", "Writing personalized emails...")

        try:
            email_data = await generate_email_with_streaming(
                campaign_name=validated.campaign_name,
                campaign_description=validated.campaign_description,
                hotel_name=validated.hotel_name,
                campaign_url=validated.campaign_url,
                target_audience=validated.target_audience,
                start_date=validated.start_date,
                end_date=validated.end_date,
            )

            result = GenerateEmailOutput(
                email_subject_en=email_data.get("email_subject_en", ""),
                email_body_en=email_data.get("email_body_en", ""),
                email_subject_zh=email_data.get("email_subject_zh", ""),
                email_body_zh=email_data.get("email_body_zh", ""),
                status="success",
            )
            await publish_event(campaign_id, "agent_completed", "Delivery Manager", "Email content ready")
            return result.model_dump()

        except Exception as e:
            await publish_event(campaign_id, "agent_error", "Delivery Manager",
                              "Email writing failed", {"error": str(e)})
            return GenerateEmailOutput(
                email_subject_en="", email_body_en="",
                email_subject_zh="", email_body_zh="",
                status="error", error=str(e),
            ).model_dump()

    async def deploy_preview(self, params: dict) -> dict:
        validated = DeployPreviewInput(**params)
        await publish_event(validated.campaign_id, "agent_started", "Delivery Manager", "Publishing preview...")

        try:
            customers_json = params.get("customers_json", "[]")
            campaign_json = params.get("campaign_json", "{}")

            try:
                preview_url = deploy_campaign_to_k8s(
                    campaign_id=validated.campaign_id,
                    html_content=validated.html_content,
                    namespace=validated.namespace or settings.DEV_NAMESPACE,
                    customers_json=customers_json,
                    campaign_json=campaign_json,
                )
            except Exception as e:
                print(f"[Delivery Manager] K8s preview deploy failed: {e}")
                preview_url = deploy_campaign_local(validated.campaign_id,
                                                   validated.namespace or settings.DEV_NAMESPACE)

            result = DeployPreviewOutput(preview_url=preview_url, status="success")
            await publish_event(validated.campaign_id, "agent_completed", "Delivery Manager",
                              "Preview published", {"preview_url": preview_url})
            return result.model_dump()

        except Exception as e:
            await publish_event(validated.campaign_id, "agent_error", "Delivery Manager",
                              "Preview publishing failed", {"error": str(e)})
            return DeployPreviewOutput(preview_url="", status="error", error=str(e)).model_dump()

    async def deploy_production(self, params: dict) -> dict:
        validated = DeployProductionInput(**params)
        await publish_event(validated.campaign_id, "agent_started", "Delivery Manager", "Going live...")

        try:
            customers_json = params.get("customers_json", "[]")
            campaign_json = params.get("campaign_json", "{}")

            try:
                production_url = deploy_campaign_to_k8s(
                    campaign_id=validated.campaign_id,
                    html_content=validated.html_content,
                    namespace=validated.namespace or settings.PROD_NAMESPACE,
                    customers_json=customers_json,
                    campaign_json=campaign_json,
                    is_preview=False,
                )
            except Exception as e:
                print(f"[Delivery Manager] K8s production deploy failed: {e}")
                production_url = deploy_campaign_local(validated.campaign_id,
                                                      validated.namespace or settings.PROD_NAMESPACE)

            result = DeployProductionOutput(production_url=production_url, status="success")
            await publish_event(validated.campaign_id, "agent_completed", "Delivery Manager",
                              "Campaign is live!", {"production_url": production_url})
            return result.model_dump()

        except Exception as e:
            await publish_event(validated.campaign_id, "agent_error", "Delivery Manager",
                              "Live deployment failed", {"error": str(e)})
            return DeployProductionOutput(production_url="", status="error", error=str(e)).model_dump()

    async def send_emails(self, params: dict) -> dict:
        validated = SendEmailsInput(**params)
        await publish_event(validated.campaign_id, "agent_started", "Delivery Manager",
                          f"Delivering to {len(validated.customers)} recipients...")

        sent_count = len(validated.customers)

        for customer in validated.customers[:5]:
            try:
                name = customer.name_en or customer.name
                campaign_url = params.get("campaign_url", "")
                personalized_link = f"{campaign_url}?c={customer.customer_id}" if campaign_url and customer.customer_id else campaign_url

                body = validated.email_body_en
                subject = validated.email_subject_en
                for placeholder in ["{{customer_name}}", "{{CUSTOMER_NAME}}", "{customer_name}", "{CUSTOMER_NAME}"]:
                    body = body.replace(placeholder, name)
                    subject = subject.replace(placeholder, name)
                for placeholder in ["{{campaign_link}}", "{{CAMPAIGN_LINK}}", "{campaign_link}", "{CAMPAIGN_LINK}"]:
                    body = body.replace(placeholder, personalized_link)
                    subject = subject.replace(placeholder, personalized_link)

                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(f"{settings.CAMPAIGN_API_URL}/api/inbox", json={
                        "from_name": brand("email_from_name", "Simon Casino Resort"),
                        "from_email": f"campaigns@{brand('email_domain', 'simoncasino.com')}",
                        "to_name": name,
                        "to_email": customer.email,
                        "subject": subject,
                        "body": body,
                        "date": datetime.datetime.utcnow().isoformat(),
                        "customer_id": customer.customer_id,
                        "campaign_url": personalized_link,
                    })
            except Exception as e:
                print(f"[Delivery Manager] Inbox POST failed for {customer.email}: {e}")

        result = SendEmailsOutput(sent_count=sent_count, status="success")
        await publish_event(validated.campaign_id, "agent_completed", "Delivery Manager",
                          f"Successfully sent to {sent_count} recipients", {"sent_count": sent_count})
        return result.model_dump()

    async def cleanup_campaign(self, params: dict) -> dict:
        campaign_id = params.get("campaign_id")
        if not campaign_id:
            return {"status": "error", "error": "campaign_id is required"}
        try:
            result = cleanup_campaign_k8s(campaign_id)
            return result
        except Exception as e:
            print(f"[Delivery Manager] Cleanup failed: {e}")
            return {"status": "error", "error": str(e)}
