import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState, TaskStatus, Part

from app.agent import PolicyGuardianAgent


class PolicyGuardianExecutor(AgentExecutor):
    def __init__(self):
        self.agent = PolicyGuardianAgent()

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
        msg = updater.new_agent_message([Part(text="Checking campaign policies...")])
        await updater.start_work(message=msg)

        try:
            user_input = context.get_user_input()
            try:
                params = json.loads(user_input)
            except (json.JSONDecodeError, TypeError):
                params = {"campaign_name": user_input, "campaign_description": user_input}
            result = await self.agent.validate(params)
            result_json = json.dumps(result, ensure_ascii=False)

            await updater.add_artifact([Part(text=result_json)])
            msg = updater.new_agent_message([Part(text="Policy check complete.")])
            await updater.complete(message=msg)
        except Exception as e:
            msg = updater.new_agent_message([Part(text=f"Policy check failed: {e}")])
            await updater.failed(message=msg)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported")
