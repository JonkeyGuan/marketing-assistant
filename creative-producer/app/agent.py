import os
import json
import httpx
import traceback

from app.settings import settings
from app.models import CAMPAIGN_THEMES
from app.config_client import get_config, prompt as vcfg_prompt, brand, themes as vcfg_themes

BASE_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "base_template.html")

PLACEHOLDER_IMAGE_URL = "https://placehold.co/1024x576/D4AF37/0F172A?text=Campaign+Hero+Image"


def is_mock_mode() -> bool:
    return not settings.MODEL_ENDPOINT


def _load_theme_preset_names() -> dict:
    cfg_themes = vcfg_themes()
    if cfg_themes:
        return {k: v.get("preset_name", k) for k, v in cfg_themes.items()}
    return {
        "luxury_gold": "The Heritage Collection",
        "festive_red": "The Celebration Suite",
        "modern_black": "The Urban Retreat",
        "classic_emerald": "The Grand Stakes",
    }

THEME_PRESET_NAMES = _load_theme_preset_names()

_CREATIVE_INTRO = vcfg_prompt(
    "creative_producer_system",
    'You are a premier Digital Brand Architect specializing in high-conversion marketing for luxury hotels and ultra-exclusive resorts. Your expertise is "Visual Hospitality" — translating a physical five-star experience into a digital interface that feels as refined and welcoming as a grand lobby.'
)

SYSTEM_PROMPT = f"""{_CREATIVE_INTRO}

## Core Design Principles:
1. "The Check-In Impression": Your designs feel like a premium arrival experience.
2. "Hospitality Typography": 'Manrope' for headlines with tight tracking.
3. "Atmospheric Color Palettes": Use the provided CSS variables exclusively.
4. "Imagery as the Main Course": The hero image is the narrative centerpiece.
5. "The Concierge CTA": Buttons are sharp-edged, high-contrast, premium language.
6. "Visual Hierarchy & Flow": Guide the eye from hero to CTA.

## Technical Rules:
- You receive a fixed semantic HTML skeleton. Do NOT output any HTML tags.
- Output a <style> block to "paint" the brand onto the structure, PLUS a content block.
- Use CSS variables: var(--primary), var(--secondary), var(--accent), var(--bg), var(--text), var(--button-color), var(--button-text)
- Style these classes creatively: body, nav, .hero, .hero-overlay, .hero .badge, .offer, .benefits, .benefits-grid, .card, .story, .dates, .date-badge, .cta-section, .cta-btn, .qr-section, footer
- Be creative with: backgrounds, card hover effects, @keyframes animations, hero overlay blend modes

## Output Format:
Return EXACTLY two sections separated by ---CONTENT---

First: a <style> block with your creative CSS (100-200 lines).
Then: ---CONTENT--- followed by key-value content lines.

Do NOT output anything else — no explanations, no HTML, no markdown fences."""


def load_base_template() -> str:
    with open(BASE_TEMPLATE_PATH, "r") as f:
        return f.read()


def parse_llm_output(raw: str) -> tuple[str, dict]:
    raw = raw.strip()
    import re
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    separator = "---CONTENT---"
    if separator not in raw:
        return raw, {}

    parts = raw.split(separator, 1)
    style_block = parts[0].strip()
    content_raw = parts[1].strip()

    content = {}
    for line in content_raw.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                content[key] = value

    return style_block, content


def merge_template(template: str, theme_config: dict, style_block: str, content: dict,
                   hero_image_url: str | None, hotel_name: str, start_date: str, end_date: str) -> str:
    html = template
    html = html.replace("THEME_PRIMARY", theme_config["primary_color"])
    html = html.replace("THEME_SECONDARY", theme_config["secondary_color"])
    html = html.replace("THEME_ACCENT", theme_config["accent_color"])
    html = html.replace("THEME_BG", theme_config.get("secondary_color", "#0a0a0a"))
    html = html.replace("THEME_TEXT", theme_config["text_color"])
    html = html.replace("THEME_BUTTON_COLOR", theme_config["button_color"])
    html = html.replace("THEME_BUTTON_TEXT", theme_config["button_text"])
    html = html.replace("LLM_STYLE_PLACEHOLDER", style_block)

    if hero_image_url:
        html = html.replace("HERO_IMAGE_PLACEHOLDER", hero_image_url)
    else:
        html = html.replace(
            "style=\"background-image: url('HERO_IMAGE_PLACEHOLDER');\"",
            "style=\"background: var(--bg);\""
        )

    html = html.replace("HOTEL_NAME", hotel_name)
    html = html.replace("DATE_START", start_date or "TBD")
    html = html.replace("DATE_END", end_date or "TBD")

    for key in ["HEADLINE", "SUBTITLE", "OFFER_TEXT",
                "BENEFIT_1_TITLE", "BENEFIT_1_DESC", "BENEFIT_2_TITLE", "BENEFIT_2_DESC",
                "BENEFIT_3_TITLE", "BENEFIT_3_DESC", "BENEFIT_4_TITLE", "BENEFIT_4_DESC",
                "STORY_TEXT"]:
        value = content.get(key, "")
        if value:
            html = html.replace(key, value)

    return html


async def generate_hero_image(campaign_name: str, hotel_name: str, theme: str, description: str = "") -> str | None:
    try:
        from fastmcp import Client
        async with Client(f"{settings.IMAGEGEN_MCP_URL}/mcp") as mcp_client:
            result = await mcp_client.call_tool("generate_campaign_image", {
                "campaign_name": campaign_name,
                "hotel_name": hotel_name,
                "theme": theme,
                "description": description,
                "width": 1024,
                "height": 576,
            })
            if result and result.content:
                data = json.loads(result.content[0].text)
                image_url = data.get("image_url")
                if image_url:
                    return image_url
        return None
    except Exception as e:
        print(f"[Creative Producer] Image gen error (non-fatal): {e}")
        return None


async def publish_event(campaign_id: str, event_type: str, agent: str, task: str, data: dict = None):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.EVENT_HUB_URL}/events/{campaign_id}/publish",
                json={"event_type": event_type, "agent": agent, "task": task, "data": data or {}},
                timeout=5.0
            )
    except Exception as e:
        print(f"[Creative Producer] Failed to publish event: {e}")


async def stream_llm(system_prompt: str, user_prompt: str) -> str:
    url = f"{settings.MODEL_ENDPOINT}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {settings.MODEL_API_KEY}"
    payload = {
        "model": settings.MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.9,
        "max_tokens": 8000,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    result = ""
    async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise Exception(f"Model API error: {response.status_code} - {error_text}")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                result += content
                    except json.JSONDecodeError:
                        continue
    return result


MOCK_STYLE = """<style>
body { background: var(--bg); }
nav { background: rgba(15, 23, 42, 0.95); border-bottom: 1px solid var(--primary); }
.hero-overlay { background: linear-gradient(135deg, rgba(15,23,42,0.8), rgba(212,175,55,0.3)); }
.hero .badge { background: var(--primary); color: var(--bg); }
.offer { background: linear-gradient(180deg, var(--bg), rgba(15,23,42,0.95)); }
.benefits { background: rgba(15,23,42,0.9); }
.card { background: rgba(212,175,55,0.08); border: 1px solid rgba(212,175,55,0.2); border-radius: 16px; }
.card:hover { border-color: var(--primary); box-shadow: 0 0 30px rgba(212,175,55,0.15); }
.story { background: var(--bg); }
.dates { background: rgba(15,23,42,0.95); }
.date-badge { background: rgba(212,175,55,0.15); color: var(--primary); border: 1px solid var(--primary); }
.cta-section { background: linear-gradient(180deg, rgba(15,23,42,0.95), var(--bg)); }
.cta-btn:hover { box-shadow: 0 0 40px rgba(212,175,55,0.4); }
.qr-section { background: var(--bg); }
footer { background: rgba(15,23,42,0.98); border-top: 1px solid rgba(212,175,55,0.2); }
@keyframes shimmer { 0% { background-position: -200% center; } 100% { background-position: 200% center; } }
.cta-btn { background: linear-gradient(90deg, var(--button-color), var(--accent), var(--button-color)); background-size: 200% auto; animation: shimmer 3s linear infinite; }
</style>"""

MOCK_CONTENT = {
    "HEADLINE": "An Exclusive Experience Awaits",
    "SUBTITLE": "Where Luxury Meets Unforgettable Moments",
    "OFFER_TEXT": "Indulge in a curated collection of exclusive privileges designed for our most distinguished guests.",
    "BENEFIT_1_TITLE": "Luxury Suite Upgrade",
    "BENEFIT_1_DESC": "Experience our finest accommodations with panoramic views and butler service.",
    "BENEFIT_2_TITLE": "Private Dining",
    "BENEFIT_2_DESC": "Savor a bespoke culinary journey crafted by our Michelin-starred chefs.",
    "BENEFIT_3_TITLE": "Spa Retreat",
    "BENEFIT_3_DESC": "Rejuvenate with our signature wellness treatments in a serene sanctuary.",
    "BENEFIT_4_TITLE": "VIP Entertainment",
    "BENEFIT_4_DESC": "Enjoy priority access to world-class performances and exclusive events.",
    "STORY_TEXT": "Step into a world where every detail is meticulously crafted to create moments of pure indulgence. Our team of dedicated professionals ensures that your experience transcends the ordinary.",
}


async def generate_html_with_streaming(
    campaign_name: str, campaign_description: str, hotel_name: str,
    theme: str, start_date: str, end_date: str, hero_image_url: str | None = None
) -> str:
    theme_config = CAMPAIGN_THEMES.get(theme, CAMPAIGN_THEMES["luxury_gold"])
    template = load_base_template()

    if is_mock_mode():
        print("[Creative Producer] Mock mode — using pre-built page")
        content = dict(MOCK_CONTENT)
        if campaign_name:
            content["HEADLINE"] = campaign_name
        if campaign_description:
            content["OFFER_TEXT"] = campaign_description
        return merge_template(template, theme_config, MOCK_STYLE, content,
                            hero_image_url, hotel_name, start_date, end_date)

    preset_name = THEME_PRESET_NAMES.get(theme, "The Heritage Collection")
    hero_note = ""
    if hero_image_url:
        hero_note = "\nThe hero section has an AI-generated background image — make it feel cinematic with overlays and blend modes."

    user_prompt = f"""Design a "{preset_name}" visual experience for "{campaign_name}" at {hotel_name}.

Color palette:
- Primary: {theme_config['primary_color']}
- Secondary: {theme_config['secondary_color']}
- Accent: {theme_config['accent_color']}
- Background: {theme_config.get('secondary_color', '#0a0a0a')}
- Text: {theme_config['text_color']}
- Button: {theme_config['button_color']} on {theme_config['button_text']}

Campaign story: {campaign_description}
Period: {start_date} to {end_date}
{hero_note}
Make the benefit cards feel luxurious (glassmorphism, gradient borders, frosted glass).
Add at least 2 @keyframes animations.

Output format — provide BOTH sections:

<style>
... your creative CSS here ...
</style>
---CONTENT---
HEADLINE: (polished campaign name)
SUBTITLE: (short tagline)
OFFER_TEXT: (1-2 sentence exclusive offer)
BENEFIT_1_TITLE: (short benefit name)
BENEFIT_1_DESC: (1 sentence)
BENEFIT_2_TITLE: (different benefit)
BENEFIT_2_DESC: (1 sentence)
BENEFIT_3_TITLE: (different benefit)
BENEFIT_3_DESC: (1 sentence)
BENEFIT_4_TITLE: (different benefit)
BENEFIT_4_DESC: (1 sentence)
STORY_TEXT: (2-3 sentences, luxury editorial tone)

ALL content must be in English only."""

    raw_response = await stream_llm(SYSTEM_PROMPT, user_prompt)

    if "<!DOCTYPE" in raw_response or "<html" in raw_response:
        html = raw_response.strip()
        if html.startswith("```html"):
            html = html[7:]
        if html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        if hero_image_url and "HERO_IMAGE_PLACEHOLDER" in html:
            html = html.replace("HERO_IMAGE_PLACEHOLDER", hero_image_url)
        return html

    style_block, content = parse_llm_output(raw_response)
    return merge_template(template, theme_config, style_block, content,
                         hero_image_url, hotel_name, start_date, end_date)


class CreativeProducerAgent:
    async def generate(self, params: dict) -> dict:
        campaign_id = params.get("campaign_id", "unknown")
        await publish_event(campaign_id, "agent_started", "Creative Producer", "Creating campaign visuals...")

        try:
            hero_image_url = await generate_hero_image(
                campaign_name=params["campaign_name"],
                hotel_name=params["hotel_name"],
                theme=params["theme"],
                description=params["campaign_description"]
            )

            if hero_image_url:
                await publish_event(campaign_id, "agent_completed", "Creative Producer",
                                  "Campaign visuals ready", {"image_url": hero_image_url})
            else:
                await publish_event(campaign_id, "workflow_status", "Creative Producer",
                                  "Applying theme design...")

            await publish_event(campaign_id, "agent_started", "Creative Producer",
                              "Designing your landing page...")

            html = await generate_html_with_streaming(
                campaign_name=params["campaign_name"],
                campaign_description=params["campaign_description"],
                hotel_name=params["hotel_name"],
                theme=params["theme"],
                start_date=params["start_date"],
                end_date=params["end_date"],
                hero_image_url=hero_image_url,
            )

            await publish_event(campaign_id, "agent_completed", "Creative Producer",
                              "Landing page ready", {"html_length": len(html)})

            return {"html": html, "hero_image_url": hero_image_url, "status": "success"}

        except Exception as e:
            traceback.print_exc()
            await publish_event(campaign_id, "agent_error", "Creative Producer",
                              "Design generation failed", {"error": str(e)})
            return {"html": "", "hero_image_url": None, "status": "error", "error": str(e)}
