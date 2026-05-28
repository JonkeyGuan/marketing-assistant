import json
import os
from functools import lru_cache
from typing import Any

from app.settings import settings

MOUNT_DIR = settings.VERTICAL_CONFIG_DIR


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    vertical_id = settings.VERTICAL_CONFIG

    candidate = os.path.join(MOUNT_DIR, f"{vertical_id}.json")
    if os.path.isfile(candidate):
        with open(candidate) as f:
            return json.load(f)

    single = os.path.join(MOUNT_DIR, "vertical.json")
    if os.path.isfile(single):
        with open(single) as f:
            return json.load(f)

    print(f"[config_loader] WARNING: No config found in {MOUNT_DIR} for '{vertical_id}', using empty defaults")
    return {}


def brand(key: str, default: str = "") -> str:
    return get_config().get("brand", {}).get(key, default)


def prompt(key: str, default: str = "") -> str:
    return get_config().get("prompts", {}).get(key, default)


def competitors() -> list[str]:
    return get_config().get("competitors", [])


def seed_data() -> dict:
    return get_config().get("seed_data", {})


def themes() -> dict:
    return get_config().get("themes", {})


def properties() -> list[str]:
    return get_config().get("properties", [])


def tiers() -> dict:
    return get_config().get("tiers", {})


def quick_start_presets() -> list[dict]:
    return get_config().get("quick_start_presets", [])
