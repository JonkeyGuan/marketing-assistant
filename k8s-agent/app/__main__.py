"""
K8s Agent — A2A server entry point.

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

from app.executor import K8sAgentExecutor
from app.settings import settings

if __name__ == '__main__':
    deploy_skill = AgentSkill(
        id='deploy_preview',
        name='Deploy Campaign Preview',
        description='Deploy a marketing campaign HTML page to the dev namespace for preview',
        tags=['k8s', 'openshift', 'deploy', 'preview'],
    )

    promote_skill = AgentSkill(
        id='promote_production',
        name='Promote to Production',
        description='Promote a marketing campaign from preview to production namespace',
        tags=['k8s', 'openshift', 'deploy', 'production'],
    )

    host = '0.0.0.0'
    port = settings.SERVICE_PORT

    agent_card = AgentCard(
        name='K8s Agent',
        description='Deploys marketing campaign pages to OpenShift (preview and production)',
        url=f'http://{host}:{port}',
        version='1.0.0',
        default_input_modes=['data'],
        default_output_modes=['data'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[deploy_skill, promote_skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=K8sAgentExecutor(),
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
