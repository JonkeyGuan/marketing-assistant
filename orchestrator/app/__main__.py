"""
Orchestrator — Streamlit UI entry point.
Start with: uv run app
"""
import os
import sys

from streamlit.web import cli as stcli
from app.settings import settings

if __name__ == "__main__":
    script = os.path.join(os.path.dirname(__file__), "ui.py")
    sys.argv = ["streamlit", "run", script, f"--server.port={settings.SERVICE_PORT}", "--server.address=0.0.0.0"]
    stcli.main()
