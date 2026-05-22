import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState, TaskStatus, Part

from app.agent import CampaignDirectorAgent


class CampaignDirectorExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CampaignDirectorAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_input = context.get_user_input()
        try:
            params = json.loads(user_input)
            skill = params.pop("skill", "create_campaign")
        except (json.JSONDecodeError, TypeError):
            params = {"text": user_input}
            skill = "chat"

        task = context.current_task
        if task is None:
            task = Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
            )
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        msg = updater.new_agent_message([Part(text=f"Processing skill: {skill}")])
        await updater.start_work(message=msg)

        result = await self.agent.handle_skill(skill, params)
        result_json = json.dumps(result)

        await updater.add_artifact([Part(text=result_json)])
        msg = updater.new_agent_message([Part(text=f"Skill '{skill}' completed.")])
        await updater.complete(message=msg)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported")
