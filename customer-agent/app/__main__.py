"""
Customer Agent — A2A server entry point.

Start with: uv run app
"""
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from app.executor import CustomerAgentExecutor
from app.settings import settings

if __name__ == '__main__':
    skill = AgentSkill(
        id='query_customers',
        name='Query Customer Profiles',
        description='Retrieve VIP customer profiles filtered by target audience, tier, or spend level',
        tags=['customer', 'crm', 'vip', 'query'],
    )

    host = '0.0.0.0'
    port = settings.SERVICE_PORT

    agent_card = AgentCard(
        name='Customer Agent',
        description='Retrieves VIP customer profiles from CRM for marketing campaigns',
        url=f'http://{host}:{port}',
        version='1.0.0',
        default_input_modes=['data'],
        default_output_modes=['data'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=CustomerAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(
        server.build(),
        host=host,
        port=port,
    )
