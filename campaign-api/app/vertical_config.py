from functools import lru_cache

import httpx

from app.settings import settings


@lru_cache(maxsize=1)
def _fetch_config() -> dict:
    resp = httpx.get(f"{settings.CONFIG_SERVICE_URL}/config", timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_config() -> dict:
    return _fetch_config()


def brand(key: str, default: str = "") -> str:
    return _fetch_config().get("brand", {}).get(key, default)


def competitors() -> list[str]:
    return _fetch_config().get("competitors", [])


def seed_data() -> dict:
    return _fetch_config().get("seed_data", {})
