import json
import logging
import traceback

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState, TaskStatus, Part

from app.agent import DeliveryManagerAgent

logger = logging.getLogger(__name__)

SKILL_DISPATCH = {
    "generate_email": "generate_email",
    "deploy_preview": "deploy_preview",
    "deploy_production": "deploy_production",
    "send_emails": "send_emails",
    "cleanup_campaign": "cleanup_campaign",
}


class DeliveryManagerExecutor(AgentExecutor):
    def __init__(self):
        self.agent = DeliveryManagerAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            task = Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
            )
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        raw_input = context.get_user_input()
        try:
            params = json.loads(raw_input)
        except (json.JSONDecodeError, TypeError):
            await updater.add_artifact([Part(text="Send structured task parameters via the Campaign Director.")])
            msg = updater.new_agent_message([Part(text="No structured input.")])
            await updater.complete(message=msg)
            return

        skill = params.pop("skill", "")
        method_name = SKILL_DISPATCH.get(skill)

        if not method_name:
            msg = updater.new_agent_message(
                [Part(text=f"Unknown skill: {skill}. Available: {list(SKILL_DISPATCH.keys())}")]
            )
            await updater.failed(message=msg)
            return

        msg = updater.new_agent_message([Part(text=f"Executing {skill}...")])
        await updater.start_work(message=msg)

        try:
            method = getattr(self.agent, method_name)
            result = await method(params)
            result_json = json.dumps(result)
            await updater.add_artifact([Part(text=result_json)])
            msg = updater.new_agent_message([Part(text=f"{skill} completed.")])
            await updater.complete(message=msg)
        except Exception as e:
            logger.exception("Delivery Manager executor failed for skill %s", skill)
            msg = updater.new_agent_message([Part(text=f"Error executing {skill}: {e}")])
            await updater.failed(message=msg)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported")
