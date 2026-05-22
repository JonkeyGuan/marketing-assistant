import subprocess
import sys

from app.settings import settings

if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "gunicorn",
        "app.server:app",
        "--bind", f"0.0.0.0:{settings.PORT}",
        "--workers", "2",
        "--threads", "2",
        "--timeout", "120",
        "--no-control-socket",
    ])
