import logging
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings


class _HealthFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/healthz" not in msg and "/readyz" not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthFilter())
from app.config_loader import (
    get_config, brand, prompt, competitors, seed_data,
    themes, properties, tiers, quick_start_presets,
)

app = FastAPI(title="Config Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "config-service"}


@app.get("/config")
def full_config():
    return get_config()


@app.get("/config/brand")
def get_brand(key: str = Query(...), default: str = Query("")):
    return {"value": brand(key, default)}


@app.get("/config/prompt")
def get_prompt(key: str = Query(...), default: str = Query("")):
    return {"value": prompt(key, default)}


@app.get("/config/competitors")
def get_competitors():
    return competitors()


@app.get("/config/seed-data")
def get_seed_data():
    return seed_data()


@app.get("/config/themes")
def get_themes():
    return themes()


@app.get("/config/properties")
def get_properties():
    return properties()


@app.get("/config/tiers")
def get_tiers():
    return tiers()


@app.get("/config/presets")
def get_presets():
    return quick_start_presets()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
