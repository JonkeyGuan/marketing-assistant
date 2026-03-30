"""
Coder Agent — A2A server entry point.

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

from app.executor import CoderAgentExecutor
from app.settings import settings

if __name__ == '__main__':
    skill = AgentSkill(
        id='generate_html',
        name='Generate Campaign HTML',
        description='Generate a complete, responsive landing page with embedded CSS/JS for a marketing campaign',
        tags=['html', 'css', 'javascript', 'marketing', 'landing-page'],
    )

    host = '0.0.0.0'
    port = settings.SERVICE_PORT

    agent_card = AgentCard(
        name='Coder Agent',
        description='Generates HTML/CSS/JS landing pages for luxury casino marketing campaigns',
        url=f'http://{host}:{port}',
        version='1.0.0',
        default_input_modes=['data'],
        default_output_modes=['data'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=CoderAgentExecutor(),
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
