import uuid
import base64
import logging
from collections import OrderedDict
from pathlib import Path

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger("imagegen_mcp")
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response
from starlette.requests import Request

from app.settings import settings
from app.vertical_config import prompt as vcfg_prompt

mcp = FastMCP("Image Generation MCP")

MAX_IMAGES = 50
image_store: OrderedDict[str, bytes] = OrderedDict()
_storage_path = Path(settings.IMAGE_STORAGE_PATH)
_disk_enabled = False


def _init_storage():
    global _disk_enabled
    try:
        _storage_path.mkdir(parents=True, exist_ok=True)
        _disk_enabled = True
        logger.info("Image disk persistence enabled: %s", _storage_path)
    except OSError as e:
        logger.info("Image disk persistence disabled (local mode): %s", e)


_init_storage()


def _store_image(image_id: str, image_bytes: bytes):
    while len(image_store) >= MAX_IMAGES:
        image_store.popitem(last=False)
    image_store[image_id] = image_bytes
    if _disk_enabled:
        try:
            (_storage_path / f"{image_id}.png").write_bytes(image_bytes)
        except OSError as e:
            logger.warning("Failed to persist image %s to disk: %s", image_id, e)


def _load_image_from_disk(image_id: str) -> bytes | None:
    if not _disk_enabled:
        return None
    path = _storage_path / f"{image_id}.png"
    if path.is_file():
        data = path.read_bytes()
        image_store[image_id] = data
        return data
    return None


_llm_client = AsyncOpenAI(
    base_url=settings.MODEL_ENDPOINT or "http://localhost:11434/v1",
    api_key=settings.MODEL_API_KEY or "unused",
    timeout=120.0,
    http_client=httpx.AsyncClient(verify=False),
)


def is_mock_mode() -> bool:
    return not settings.MODEL_ENDPOINT or not settings.MODEL_API_KEY

THEME_PROMPTS = {
    "luxury_gold": "golden champagne tones, warm amber lighting, elegant marble and crystal, luxurious atmosphere",
    "festive_red": "vibrant crimson and gold, festive lanterns, celebration atmosphere, rich silk textures",
    "modern_black": "sleek monochrome, silver accents, futuristic minimalism, dramatic shadows, architectural lines",
    "classic_emerald": "deep emerald green felt, gold and brass accents, classic elegance, vintage glamour",
}

PLACEHOLDER_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="

PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _build_prompt(campaign_name: str, hotel_name: str, theme: str, description: str = "") -> str:
    import random
    theme_style = THEME_PROMPTS.get(theme, THEME_PROMPTS["luxury_gold"])
    image_context = vcfg_prompt(
        "creative_producer_image",
        "luxury casino hotel atmosphere, golden hour, Macau skyline, VIP atmosphere, architectural photography, cinematic lighting"
    )
    angles = [
        "aerial drone shot", "wide-angle lobby view", "intimate close-up detail",
        "sweeping panoramic vista", "dramatic low-angle perspective",
        "bird's-eye overhead composition", "twilight silhouette shot",
        "reflective water surface composition",
    ]
    times = ["golden hour", "blue hour twilight", "midnight ambiance", "sunrise glow", "sunset warmth"]
    subjects = [
        "grand hotel lobby with chandeliers and marble floors",
        "infinity pool overlooking city skyline at night",
        "luxurious VIP lounge with velvet seating and ambient lighting",
        "rooftop terrace with panoramic ocean views",
        "elegant ballroom with crystal decorations",
        "private casino suite with felt tables and golden accents",
        "spa retreat with zen garden and water features",
        "fine dining restaurant with candlelight and wine cellar",
        "penthouse suite with floor-to-ceiling windows",
        "tropical resort garden pathway with lanterns",
    ]
    moods = [
        "mysterious and moody with deep shadows",
        "bright and airy with natural light flooding in",
        "warm and intimate with soft bokeh lights",
        "grand and majestic with imposing architecture",
        "serene and tranquil with minimalist composition",
        "vibrant and energetic with rich saturated colors",
    ]
    chosen_angle = random.choice(angles)
    chosen_time = random.choice(times)
    chosen_subject = random.choice(subjects)
    chosen_mood = random.choice(moods)
    seed = random.randint(1000, 9999)
    return (
        f"Professional photography, {theme_style}. "
        f"{chosen_subject}, {chosen_mood}, "
        f"{image_context}, "
        f"{chosen_angle}, {chosen_time}, "
        f"photorealistic, ultra high quality, 4K resolution, "
        f"wide banner composition, seed:{seed}. "
        f"ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO LOGOS, NO WATERMARKS, NO TYPOGRAPHY in the image. "
        f"Pure photography only, no graphic design elements."
    )


async def _call_imagegen_api(prompt: str, width: int = 1024, height: int = 576) -> bytes:
    response = await _llm_client.images.generate(
        model=settings.MODEL_NAME,
        prompt=prompt,
        size=f"{width}x{height}",
        response_format="b64_json",
    )
    return base64.b64decode(response.data[0].b64_json)


@mcp.tool
async def generate_campaign_image(
    campaign_name: str,
    hotel_name: str = "Simon Casino Resort",
    theme: str = "luxury_gold",
    description: str = "",
    width: int = 1024,
    height: int = 576,
) -> dict:
    """Generate a marketing hero banner and return a URL to the image.

    Args:
        campaign_name: Name of the marketing campaign
        hotel_name: Hotel/casino name for branding
        theme: Visual theme (luxury_gold, festive_red, modern_black, classic_emerald)
        description: Optional campaign description for prompt context
        width: Image width in pixels
        height: Image height in pixels
    """
    image_id = f"img-{uuid.uuid4().hex[:12]}"
    prompt = _build_prompt(campaign_name, hotel_name, theme, description)

    if is_mock_mode():
        _store_image(image_id, PLACEHOLDER_PNG)
        return {
            "image_url": f"/images/{image_id}.png",
            "image_id": image_id,
            "prompt": prompt,
            "status": "success",
            "mock": True,
        }

    image_bytes = await _call_imagegen_api(prompt, width, height)
    _store_image(image_id, image_bytes)
    return {
        "image_url": f"/images/{image_id}.png",
        "image_id": image_id,
        "prompt": prompt,
        "status": "success",
    }


@mcp.tool
async def generate_campaign_image_b64(
    campaign_name: str,
    hotel_name: str = "Simon Casino Resort",
    theme: str = "luxury_gold",
    description: str = "",
    width: int = 1024,
    height: int = 576,
) -> dict:
    """Generate a marketing hero banner and return as base64 data URI.

    Args:
        campaign_name: Name of the marketing campaign
        hotel_name: Hotel/casino name for branding
        theme: Visual theme (luxury_gold, festive_red, modern_black, classic_emerald)
        description: Optional campaign description for prompt context
        width: Image width in pixels
        height: Image height in pixels
    """
    if is_mock_mode():
        image_id = f"img-{uuid.uuid4().hex[:12]}"
        return {
            "data_uri": PLACEHOLDER_B64,
            "image_id": image_id,
            "prompt": _build_prompt(campaign_name, hotel_name, theme, description),
            "status": "success",
            "mock": True,
        }

    prompt = _build_prompt(campaign_name, hotel_name, theme, description)
    image_bytes = await _call_imagegen_api(prompt, width, height)

    image_id = f"img-{uuid.uuid4().hex[:12]}"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "data_uri": f"data:image/png;base64,{b64}",
        "image_id": image_id,
        "prompt": prompt,
        "status": "success",
    }


async def serve_image(request: Request):
    filename = request.path_params["filename"]
    image_id = filename.replace(".png", "")
    data = image_store.get(image_id) or _load_image_from_disk(image_id)
    if data is None:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def health(request: Request):
    return JSONResponse({
        "status": "healthy",
        "service": "Image Generation MCP",
        "mock_mode": is_mock_mode(),
    })


mcp_app = mcp.http_app(path="/mcp")

app = Starlette(
    routes=[
        Route("/healthz", health, methods=["GET"]),
        Route("/readyz", health, methods=["GET"]),
        Route("/images/{filename}", serve_image, methods=["GET"]),
        Mount("/", app=mcp_app),
    ],
    lifespan=mcp_app.lifespan,
)
