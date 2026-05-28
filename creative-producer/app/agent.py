import json
import os
import traceback
from contextlib import nullcontext

import httpx
import mlflow
from mlflow.entities import SpanType
from openai import AsyncOpenAI

from app.schemas import CAMPAIGN_THEMES
from app.settings import settings
from app.vertical_config import brand, prompt as vcfg_prompt, themes as vcfg_themes

BASE_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "base_template.html")

PLACEHOLDER_IMAGE_URL = "https://placehold.co/1024x576/D4AF37/0F172A?text=Campaign+Hero+Image"

_llm_client = AsyncOpenAI(
    base_url=settings.MODEL_ENDPOINT or "http://localhost:11434/v1",
    api_key=settings.MODEL_API_KEY or "unused",
    timeout=300.0,
    http_client=httpx.AsyncClient(verify=False),
)


def is_mock_mode() -> bool:
    return not settings.MODEL_ENDPOINT


_theme_preset_names_cache = None


def _get_theme_preset_names() -> dict:
    global _theme_preset_names_cache
    if _theme_preset_names_cache is None:
        cfg_themes = vcfg_themes()
        if cfg_themes:
            _theme_preset_names_cache = {k: v.get("preset_name", k) for k, v in cfg_themes.items()}
        else:
            _theme_preset_names_cache = {
                "luxury_gold": "The Heritage Collection",
                "festive_red": "The Celebration Suite",
                "modern_black": "The Urban Retreat",
                "classic_emerald": "The Grand Stakes",
            }
    return _theme_preset_names_cache


_system_prompt_cache = None


def _get_system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is not None:
        return _system_prompt_cache
    intro = vcfg_prompt(
        "creative_producer_system",
        'You are a premier Digital Brand Architect specializing in high-conversion marketing for luxury hotels and ultra-exclusive resorts. Your expertise is "Visual Hospitality" — translating a physical five-star experience into a digital interface that feels as refined and welcoming as a grand lobby.'
    )
    _system_prompt_cache = f"""{intro}

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
    return _system_prompt_cache


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
    stream = await _llm_client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        max_tokens=8000,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    result = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            result += chunk.choices[0].delta.content
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

    import random
    preset_name = _get_theme_preset_names().get(theme, "The Heritage Collection")
    hero_note = ""
    if hero_image_url:
        hero_note = "\nThe hero section has an AI-generated background image — make it feel cinematic with overlays and blend modes."

    style_moods = [
        "Art Deco grandeur with geometric patterns and bold symmetry",
        "Minimalist zen with generous white space and subtle gradients",
        "Baroque opulence with ornate borders and rich layering",
        "Contemporary editorial with asymmetric layouts and bold typography",
        "Tropical luxe with warm tones and organic flowing shapes",
        "Nordic elegance with clean lines and muted sophistication",
        "Hollywood glamour with dramatic lighting and metallic accents",
        "Japanese wabi-sabi with textured surfaces and understated beauty",
    ]

    card_styles = [
        "glassmorphism with frosted glass effect and subtle blur",
        "neumorphism with soft shadows and raised surfaces",
        "gradient borders with animated color shifts",
        "dark glass panels with neon edge glow",
        "textured paper with embossed lettering feel",
        "floating cards with parallax depth shadows",
    ]

    hero_overlays = [
        "diagonal split overlay with gradient from primary to transparent",
        "radial vignette darkening from edges to center spotlight",
        "cinematic letterbox with horizontal gradient bands",
        "mesh gradient overlay blending primary and accent colors",
        "duotone filter using primary and secondary colors",
        "film grain texture overlay with soft color wash",
    ]

    animation_styles = [
        "smooth fade-in with staggered delays for each section",
        "slide-up reveal animations triggered on scroll",
        "subtle pulse and glow effects on interactive elements",
        "typewriter text reveal for headlines",
        "floating particle or shimmer background effects",
        "wave motion on borders and decorative elements",
    ]

    headline_tones = [
        "mysterious and intriguing, like a secret invitation",
        "bold and confident, commanding attention",
        "warm and welcoming, like greeting an old friend",
        "poetic and evocative, painting a sensory picture",
        "playful and surprising, breaking luxury conventions",
        "understated and exclusive, implying hidden privilege",
    ]

    chosen_mood = random.choice(style_moods)
    chosen_cards = random.choice(card_styles)
    chosen_overlay = random.choice(hero_overlays)
    chosen_animation = random.choice(animation_styles)
    chosen_tone = random.choice(headline_tones)
    seed = random.randint(1000, 9999)

    user_prompt = f"""Design a "{preset_name}" visual experience for "{campaign_name}" at {hotel_name}.
[variation-seed: {seed}]

Creative direction: {chosen_mood}.
Write ALL headlines and copy in a tone that is {chosen_tone}.

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
CARD STYLE: Use {chosen_cards} for the benefit cards.
HERO OVERLAY: Apply {chosen_overlay} on the hero section.
ANIMATIONS: Implement {chosen_animation}. Add at least 2 @keyframes.

IMPORTANT: Each generation must look distinctly different. Be creative and bold with your CSS choices.

Output format — provide BOTH sections:

<style>
... your creative CSS here (be bold, make it unique!) ...
</style>
---CONTENT---
HEADLINE: (create a unique, evocative headline — NOT just the campaign name)
SUBTITLE: (a fresh tagline that matches the {chosen_tone} tone)
OFFER_TEXT: (1-2 sentence exclusive offer, written creatively)
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

    raw_response = await stream_llm(_get_system_prompt(), user_prompt)

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


def _restore_trace_context(headers):
    if headers and "traceparent" in headers:
        from mlflow.tracing import set_tracing_context_from_http_request_headers
        return set_tracing_context_from_http_request_headers(headers)
    return nullcontext()


class CreativeProducerAgent:
    async def generate(self, params: dict, agent_headers: dict = None) -> dict:
        campaign_id = params.get("campaign_id", "unknown")

        await publish_event(campaign_id, "agent_started", "Creative Producer", "Creating campaign visuals...")

        try:
            with _restore_trace_context(agent_headers):
                with mlflow.start_span("creative_producer", span_type=SpanType.AGENT) as span:
                    span._span.set_attribute("session.id", campaign_id)
                    span.set_inputs(params)

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

                    result = {"html": html, "hero_image_url": hero_image_url, "status": "success"}
                    span.set_outputs(result)
                    return result

        except Exception as e:
            traceback.print_exc()
            await publish_event(campaign_id, "agent_error", "Creative Producer",
                              "Design generation failed", {"error": str(e)})
            return {"html": "", "hero_image_url": None, "status": "error", "error": str(e)}
