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
from starlette.requests import Request

from app.agent_executor import CampaignDirectorExecutor
from app.agent import campaigns_store

host = "0.0.0.0"
agent_endpoint = settings.AGENT_ENDPOINT or f"http://localhost:{settings.PORT}"

agent_card = AgentCard(
    name="Campaign Director",
    description="Orchestrates marketing campaign creation workflow using LangGraph",
    version="1.0.0",
    supported_interfaces=[AgentInterface(url=f"{agent_endpoint}/", protocol_binding="JSONRPC")],
    default_input_modes=["text", "text/plain"],
    default_output_modes=["text", "text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(id="create_campaign", name="Create Campaign",
                   description="Create a new marketing campaign",
                   tags=["campaign", "create"]),
        AgentSkill(id="generate_landing_page", name="Generate Landing Page",
                   description="Generate landing page for an existing campaign",
                   tags=["campaign", "landing-page"]),
        AgentSkill(id="prepare_email_preview", name="Prepare Email Preview",
                   description="Retrieve customers and generate email content",
                   tags=["campaign", "email"]),
        AgentSkill(id="go_live", name="Go Live",
                   description="Deploy campaign to production and send emails",
                   tags=["campaign", "deploy"]),
        AgentSkill(id="delete_campaign", name="Delete Campaign",
                   description="Delete a campaign and clean up all K8s resources",
                   tags=["campaign", "delete"]),
    ],
)

handler = DefaultRequestHandler(
    agent_executor=CampaignDirectorExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)


async def health_check(request: Request):
    return JSONResponse({"status": "healthy", "agent": "Campaign Director"})


async def list_campaigns(request: Request):
    return JSONResponse([c.model_dump(mode="json") for c in campaigns_store.values()])


async def get_campaign(request: Request):
    campaign_id = request.path_params["campaign_id"]
    if campaign_id not in campaigns_store:
        return JSONResponse({"error": "Campaign not found"}, status_code=404)
    return JSONResponse(campaigns_store[campaign_id].model_dump(mode="json"))


app = Starlette(
    routes=[
        Route("/healthz", health_check, methods=["GET"]),
        Route("/readyz", health_check, methods=["GET"]),
        Route("/campaigns", list_campaigns, methods=["GET"]),
        Route("/campaigns/{campaign_id}", get_campaign, methods=["GET"]),
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/"),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host=host, port=settings.PORT)
