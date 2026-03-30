"""
K8s Agent Executor

Implements the A2A AgentExecutor interface.
Receives campaign data via A2A message, deploys to OpenShift, returns URLs.
"""
import logging
import uuid

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Artifact,
    DataPart,
    Part,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils.message import new_agent_text_message
from a2a.utils.task import new_task

from app.deploy import deploy_preview, promote_production

logger = logging.getLogger(__name__)


class K8sAgentExecutor(AgentExecutor):
    """A2A executor that deploys marketing campaigns to OpenShift."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        # Extract request data from incoming message DataPart
        data: dict = {}
        if context.message and context.message.parts:
            for part in context.message.parts:
                inner = part.root
                if isinstance(inner, DataPart) and inner.data:
                    data = dict(inner.data)
                    break

        action = data.get("action", "deploy_preview")
        campaign_id = data.get("campaign_id", "campaign")

        # Signal: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=False,
                status=TaskStatus(
                    state=TaskState.working,
                    message=new_agent_text_message(
                        f"Deploying campaign '{campaign_id}' ({action})"
                    ),
                ),
            )
        )

        try:
            generated_html = data.get("generated_html", "")

            if action == "promote_production":
                logger.info("Promoting to production: %s", campaign_id)
                result = promote_production(campaign_id, generated_html)
            else:
                logger.info("Deploying preview: %s", campaign_id)
                result = deploy_preview(campaign_id, generated_html)

            logger.info("Deploy succeeded: %s", result)

            # Emit artifact with deployment result
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid.uuid4()),
                        name="deploy_result",
                        parts=[
                            Part(root=DataPart(data=result))
                        ],
                    ),
                )
            )

            # Signal: completed
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=True,
                    status=TaskStatus(state=TaskState.completed),
                )
            )

        except Exception as e:
            logger.error("Error: %s", e)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=new_agent_text_message(str(e)),
                    ),
                )
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError("cancel not supported")
