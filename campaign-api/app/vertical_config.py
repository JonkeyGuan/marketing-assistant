import httpx

from app.settings import settings


_config_cache: dict | None = None


def _fetch_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    try:
        resp = httpx.get(f"{settings.CONFIG_SERVICE_URL}/config", timeout=10)
        resp.raise_for_status()
        _config_cache = resp.json()
        return _config_cache
    except Exception:
        return {}


def get_config() -> dict:
    return _fetch_config()


def brand(key: str, default: str = "") -> str:
    return _fetch_config().get("brand", {}).get(key, default)


def competitors() -> list[str]:
    return _fetch_config().get("competitors", [])


def seed_data() -> dict:
    return _fetch_config().get("seed_data", {})
