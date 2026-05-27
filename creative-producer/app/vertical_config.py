import httpx
from functools import lru_cache
from app.settings import settings


@lru_cache(maxsize=1)
def _fetch_config() -> dict:
    resp = httpx.get(f"{settings.CONFIG_SERVICE_URL}/config")
    resp.raise_for_status()
    return resp.json()


def brand(key: str, default: str = "") -> str:
    return _fetch_config().get("brand", {}).get(key, default)


def prompt(key: str, default: str = "") -> str:
    return _fetch_config().get("prompts", {}).get(key, default)


def themes() -> dict:
    return _fetch_config().get("themes", {})
