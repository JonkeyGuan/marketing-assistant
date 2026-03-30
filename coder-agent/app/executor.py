"""
Coder Agent Executor

Implements the A2A AgentExecutor interface.
Receives campaign data via A2A message, generates HTML, returns as artifact.
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

from app.generate_html import generate_campaign_html

logger = logging.getLogger(__name__)


class CoderAgentExecutor(AgentExecutor):
    """A2A executor that generates marketing campaign HTML pages."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        # Create or resume task
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        # Extract campaign data from incoming message DataPart
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
                        f"Generating HTML for: {campaign_name}"
                    ),
                ),
            )
        )

        try:
            logger.info("[Coder Agent] Generating HTML for: %s", campaign_name)

            html = generate_campaign_html(
                campaign_name=data.get("campaign_name", ""),
                campaign_description=data.get("campaign_description", ""),
                hotel_name=data.get("hotel_name", "Galaxy Macau"),
                theme_colors=data.get("theme_colors", {}),
                theme_name=data.get("theme_name", "luxury_gold"),
                start_date=data.get("start_date", ""),
                end_date=data.get("end_date", ""),
            )

            logger.info("[Coder Agent] Generated %d bytes of HTML", len(html))

            # Emit artifact with generated HTML
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid.uuid4()),
                        name="campaign_html",
                        parts=[
                            Part(root=DataPart(data={"generated_html": html}))
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
            logger.error("[Coder Agent] Error: %s", e)
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
