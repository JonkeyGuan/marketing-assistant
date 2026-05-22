import logging
import uvicorn
from app.settings import settings
from app.server import app


class _HealthFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/healthz" not in msg and "/readyz" not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthFilter())

if __name__ == "__main__":
    print(f"[ImageGen MCP] Starting on 0.0.0.0:{settings.PORT}")
    print(f"[ImageGen MCP] MCP endpoint: http://0.0.0.0:{settings.PORT}/mcp")
    print(f"[ImageGen MCP] Image serving: http://0.0.0.0:{settings.PORT}/images/")
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
