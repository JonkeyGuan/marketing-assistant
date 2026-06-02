import logging

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentInterface
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Route
from starlette.responses import JSONResponse

from app.settings import settings
from app.agent import _auth_header
from app.agent_executor import CustomerAnalystExecutor
from app.tracing import setup_telemetry, TraceContextMiddleware

level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


class _HealthFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/healthz" not in msg and "/readyz" not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthFilter())
setup_telemetry()

host = "0.0.0.0"
agent_endpoint = settings.AGENT_ENDPOINT or f"http://localhost:{settings.PORT}"

agent_card = AgentCard(
    name="Customer Analyst",
    description="Retrieves VIP customer profiles for marketing campaign targeting via MCP",
    version="1.0.0",
    supported_interfaces=[AgentInterface(url=f"{agent_endpoint}/", protocol_binding="JSONRPC")],
    default_input_modes=["text", "text/plain"],
    default_output_modes=["text", "text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="get_target_customers",
            name="Get Target Customers",
            description="Retrieve customers matching target audience criteria",
            tags=["customers", "targeting", "vip"],
            examples=["Get all Platinum tier VIP customers"],
        )
    ],
)

handler = DefaultRequestHandler(
    agent_executor=CustomerAnalystExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)


async def health_check(request):
    return JSONResponse({"status": "healthy", "agent": "Customer Analyst"})


class AuthCapture(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = _auth_header.set(request.headers.get("Authorization", ""))
        try:
            return await call_next(request)
        finally:
            _auth_header.reset(token)


app = Starlette(
    routes=[
        Route("/healthz", health_check, methods=["GET"]),
        Route("/readyz", health_check, methods=["GET"]),
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/", enable_v0_3_compat=True),
    ],
    middleware=[Middleware(AuthCapture)],
)
app.add_middleware(TraceContextMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host=host, port=settings.PORT)
