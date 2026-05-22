"""
Event Hub — SSE broadcast service (gunicorn + Flask).
Local: uv run app | Container: python -m app
"""
import subprocess
import sys

from app.settings import settings

if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "gunicorn",
        "app.server:app",
        "--bind", f"0.0.0.0:{settings.PORT}",
        "--worker-class", "gthread",
        "--workers", "1",
        "--threads", "4",
        "--timeout", "0",
        "--no-control-socket",
    ])
