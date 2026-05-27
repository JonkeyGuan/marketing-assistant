import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState, TaskStatus, Part

from app.agent import PolicyGuardianAgent


def get_a2a_agent_headers(context: RequestContext) -> dict:
    agent_headers = (getattr(context.call_context, "state", {}) or {}).get("headers", {})
    if not agent_headers:
        from app.tracing import get_trace_headers
        agent_headers = get_trace_headers()
    return agent_headers


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
            agent_headers = get_a2a_agent_headers(context)
            result = await self.agent.validate(params, agent_headers)
            result_json = json.dumps(result, ensure_ascii=False)

            await updater.add_artifact([Part(text=result_json)])
            if result.get("approved"):
                summary = "APPROVED"
            else:
                summary = f"REJECTED: {result.get('reason', 'Policy violation')}"
            msg = updater.new_agent_message([Part(text=summary)])
            await updater.complete(message=msg)
        except Exception as e:
            msg = updater.new_agent_message([Part(text=f"Policy check failed: {e}")])
            await updater.failed(message=msg)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported")
