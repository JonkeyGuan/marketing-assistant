import httpx
from functools import lru_cache
from app.settings import settings


@lru_cache(maxsize=1)
def _fetch_config() -> dict:
    resp = httpx.get(f"{settings.CONFIG_SERVICE_URL}/config")
    resp.raise_for_status()
    return resp.json()


def prompt(key: str, default: str = "") -> str:
    return _fetch_config().get("prompts", {}).get(key, default)


def seed_data() -> dict:
    return _fetch_config().get("seed_data", {})
