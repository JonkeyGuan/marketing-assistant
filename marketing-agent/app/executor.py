"""
Marketing Agent Executor

Implements the A2A AgentExecutor interface.
Receives campaign data via A2A message, generates bilingual email content,
returns as artifact.
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

from app.generate_email import generate_email_content

logger = logging.getLogger(__name__)


class MarketingAgentExecutor(AgentExecutor):
    """A2A executor that generates marketing email content."""

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

        campaign_name = data.get("campaign_name", "unknown")

        # Signal: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=False,
                status=TaskStatus(
                    state=TaskState.working,
                    message=new_agent_text_message(
                        f"Generating email content for: {campaign_name}"
                    ),
                ),
            )
        )

        try:
            logger.info("Generating email content for: %s", campaign_name)

            email_content = generate_email_content(
                campaign_name=data.get("campaign_name", ""),
                campaign_description=data.get("campaign_description", ""),
                hotel_name=data.get("hotel_name", ""),
                campaign_url=data.get("campaign_url", ""),
                target_audience=data.get("target_audience", ""),
                start_date=data.get("start_date", ""),
                end_date=data.get("end_date", ""),
            )

            logger.info("Generated email content for: %s", campaign_name)

            # Emit artifact with email content
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid.uuid4()),
                        name="email_content",
                        parts=[
                            Part(root=DataPart(data=email_content))
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
