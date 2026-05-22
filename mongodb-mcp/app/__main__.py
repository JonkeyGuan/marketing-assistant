import logging
from app.settings import settings

level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


class _HealthFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/healthz" not in msg and "/readyz" not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthFilter())

from app.seed_data import seed
from app.server import app

if __name__ == "__main__":
    import uvicorn
    seed()
    print(f"[MongoDB MCP] Starting on 0.0.0.0:{settings.PORT}")
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
