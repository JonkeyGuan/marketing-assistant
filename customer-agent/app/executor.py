"""
Customer Agent Executor

Implements the A2A AgentExecutor interface.
Receives target_audience via A2A message, queries customers, returns as artifact.
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

from app.customer_query import query_by_target_audience

logger = logging.getLogger(__name__)


class CustomerAgentExecutor(AgentExecutor):
    """A2A executor that retrieves customer profiles for marketing campaigns."""

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

        target_audience = data.get("target_audience", "")

        # Signal: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=False,
                status=TaskStatus(
                    state=TaskState.working,
                    message=new_agent_text_message(
                        f"Querying customers for: {target_audience}"
                    ),
                ),
            )
        )

        try:
            logger.info("Querying customers for: %s", target_audience)

            customers = query_by_target_audience(target_audience)

            logger.info("Retrieved %d customers", len(customers))

            # Emit artifact with customer list
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid.uuid4()),
                        name="customer_list",
                        parts=[
                            Part(root=DataPart(data={"customers": customers}))
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
