"""Task manager agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class TaskManagerAgent(BaseAgent):
    name: ClassVar[str] = "Task Manager"
    slug: ClassVar[str] = "task-manager"
    description: ClassVar[str] = "List, cancel, and retry Angie tasks."
    capabilities: ClassVar[list[str]] = ["task", "cancel task", "retry task", "list tasks"]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        async def list_tasks(status: str = "", limit: int = 20) -> dict:
            """List Angie tasks, optionally filtered by status."""
            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.task import Task, TaskStatus

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
                if status:
                    try:
                        stmt = stmt.where(Task.status == TaskStatus(status))
                    except ValueError:
                        return {"error": f"Invalid status: {status}"}
                result = await session.execute(stmt)
                tasks = result.scalars().all()
                return {
                    "tasks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "status": t.status.value,
                            "source_channel": t.source_channel,
                            "created_at": str(t.created_at),
                            "error": t.error,
                        }
                        for t in tasks
                    ]
                }

        @agent.tool_plain
        def cancel_task(task_id: str) -> dict:
            """Cancel a running Angie task by its ID."""
            from angie.queue.celery_app import celery_app

            celery_app.control.revoke(task_id, terminate=True)
            return {"cancelled": True, "task_id": task_id}

        @agent.tool_plain
        async def retry_task(task_id: str) -> dict:
            """Retry a previously failed Angie task by its ID."""
            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.task import Task, TaskStatus
            from angie.queue.workers import execute_task

            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if not task:
                    return {"error": f"Task {task_id} not found"}
                if task.status not in (TaskStatus.FAILURE, TaskStatus.CANCELLED):
                    return {"error": f"Task {task_id} is {task.status.value}, not retryable"}
                task.status = TaskStatus.QUEUED
                task.retry_count += 1
                task.error = None
                await session.commit()
                celery_result = execute_task.delay(task.id)
                return {"retried": True, "task_id": task.id, "celery_id": celery_result.id}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list tasks")
        self.logger.info("TaskManagerAgent intent=%r", intent)
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("TaskManagerAgent error")
            return {"error": str(exc)}
