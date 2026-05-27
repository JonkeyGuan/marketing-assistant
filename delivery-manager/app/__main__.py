from app.tracing import setup_telemetry
setup_telemetry()

import logging
from app.settings import settings

level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


class _HealthFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/healthz" not in msg and "/readyz" not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthFilter())

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentInterface
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from app.agent_executor import DeliveryManagerExecutor
from app.tracing import TraceContextMiddleware

host = "0.0.0.0"
agent_endpoint = settings.AGENT_ENDPOINT or f"http://localhost:{settings.PORT}"

agent_card = AgentCard(
    name="Delivery Manager",
    description="Generates marketing emails and deploys campaigns",
    version="1.0.0",
    supported_interfaces=[AgentInterface(url=f"{agent_endpoint}/", protocol_binding="JSONRPC")],
    default_input_modes=["text", "text/plain"],
    default_output_modes=["text", "text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(id="generate_email", name="Generate Email",
                   description="Generate marketing email content in English and Chinese",
                   tags=["email", "marketing", "bilingual"]),
        AgentSkill(id="deploy_preview", name="Deploy Preview",
                   description="Deploy campaign landing page to preview environment",
                   tags=["deploy", "preview"]),
        AgentSkill(id="deploy_production", name="Deploy Production",
                   description="Deploy campaign landing page to production",
                   tags=["deploy", "production"]),
        AgentSkill(id="send_emails", name="Send Emails",
                   description="Send marketing emails to customer list (simulated)",
                   tags=["email", "send"]),
        AgentSkill(id="cleanup_campaign", name="Cleanup Campaign",
                   description="Delete all K8s resources for a campaign (preview and production)",
                   tags=["deploy", "cleanup"]),
    ],
)

handler = DefaultRequestHandler(
    agent_executor=DeliveryManagerExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)


async def health_check(request):
    return JSONResponse({"status": "healthy", "agent": "Delivery Manager"})


app = Starlette(
    routes=[
        Route("/healthz", health_check, methods=["GET"]),
        Route("/readyz", health_check, methods=["GET"]),
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/", enable_v0_3_compat=True),
    ],
    middleware=[],
)
app.add_middleware(TraceContextMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host=host, port=settings.PORT)
