"""Main Runner class for langchain-runner."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypeVar

from langchain_runner.adapters import AgentAdapter, create_adapter
from langchain_runner.models import RunStatus, TriggerType
from langchain_runner.store import RunStore
from langchain_runner.triggers import Trigger

F = TypeVar("F", bound=Callable[..., Any])


class Runner:
    """Main runner class that wraps an agent and exposes triggers.

    Example:
        ```python
        from langchain_runner import Runner

        agent = create_react_agent(model, tools)
        runner = Runner(agent)

        @runner.trigger("/ask")
        async def ask(question: str):
            return question

        @runner.webhook("/github")
        async def on_github(payload: dict):
            return f"Review PR: {payload['title']}"

        @runner.cron("0 9 * * *")
        async def daily():
            return "Generate daily report"

        runner.serve()
        ```
    """

    def __init__(
        self,
        agent: Any,
        *,
        name: str | None = None,
        max_runs: int = 1000,
    ) -> None:
        """Initialize the Runner.

        Args:
            agent: The agent to run. Can be a LangGraph CompiledGraph,
                   async callable, or sync callable.
            name: Optional name for this runner (used in health endpoint).
            max_runs: Maximum number of runs to keep in memory.
        """
        self.name = name
        self.adapter: AgentAdapter = create_adapter(agent)
        self.store = RunStore(max_runs=max_runs)
        self._triggers: dict[str, Trigger] = {}
        self._cron_triggers: list[Trigger] = []

    def trigger(self, path: str) -> Callable[[F], F]:
        """Register an HTTP trigger.

        The decorated function receives the request body as kwargs
        and returns the input for the agent.

        Args:
            path: The path suffix for this trigger (e.g., "/ask" -> POST /trigger/ask).

        Example:
            ```python
            @runner.trigger("/ask")
            async def ask(question: str):
                return question
            ```
        """
        # Normalize path
        name = path.strip("/")

        def decorator(func: F) -> F:
            trigger = Trigger(name=name, handler=func, trigger_type=TriggerType.HTTP)
            self._triggers[name] = trigger
            return func

        return decorator

    def webhook(self, path: str) -> Callable[[F], F]:
        """Register a webhook trigger.

        The decorated function receives the raw webhook payload
        and returns the input for the agent.

        Args:
            path: The path suffix for this trigger (e.g., "/github" -> POST /webhook/github).

        Example:
            ```python
            @runner.webhook("/github")
            async def on_github(payload: dict):
                return f"Review PR: {payload['pull_request']['title']}"
            ```
        """
        name = path.strip("/")

        def decorator(func: F) -> F:
            trigger = Trigger(name=name, handler=func, trigger_type=TriggerType.WEBHOOK)
            self._triggers[name] = trigger
            return func

        return decorator

    def cron(self, schedule: str) -> Callable[[F], F]:
        """Register a cron trigger.

        The decorated function is called on the schedule
        and returns the input for the agent.

        Args:
            schedule: Cron expression (e.g., "0 9 * * *" for daily at 9am).

        Example:
            ```python
            @runner.cron("0 9 * * *")
            async def daily_summary():
                return "Generate daily standup summary"
            ```
        """

        def decorator(func: F) -> F:
            name = func.__name__
            trigger = Trigger(
                name=name, handler=func, trigger_type=TriggerType.CRON, schedule=schedule
            )
            self._triggers[name] = trigger
            self._cron_triggers.append(trigger)
            return func

        return decorator

    async def run_agent(self, trigger: Trigger, input: str | dict) -> str:
        """Execute the agent and track the run.

        Args:
            trigger: The trigger that initiated this run.
            input: The input for the agent.

        Returns:
            The run_id for tracking.
        """
        # Create run record
        run = self.store.create_run(
            trigger_type=trigger.trigger_type,
            trigger_name=trigger.name,
            input=input,
        )

        # Start background execution
        await self._execute_run(run.run_id, input)

        return run.run_id

    async def _execute_run(self, run_id: str, input: str | dict) -> None:
        """Execute the agent in the background."""
        self.store.update_run(run_id, status=RunStatus.RUNNING)

        try:
            result = await self.adapter.invoke(input)
            final_message = self.adapter.extract_final_message(result)

            # Convert result to JSON-serializable format
            serializable_result = self._make_serializable(result)

            self.store.update_run(
                run_id,
                status=RunStatus.COMPLETED,
                result=serializable_result,
                final_message=final_message,
            )
        except Exception as e:
            self.store.update_run(
                run_id,
                status=RunStatus.FAILED,
                error=str(e),
            )

    def _make_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        # For LangChain message objects and other complex types
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        return str(obj)

    def get_triggers(self) -> list[Trigger]:
        """Get all registered triggers."""
        return list(self._triggers.values())

    def get_cron_triggers(self) -> list[Trigger]:
        """Get all registered cron triggers."""
        return self._cron_triggers

    def serve(
        self,
        host: str | None = None,
        port: int | None = None,
        **uvicorn_kwargs: Any,
    ) -> None:
        """Start the server.

        Args:
            host: Host to bind to. Defaults to LANGCHAIN_RUNNER_HOST or "0.0.0.0".
            port: Port to bind to. Defaults to LANGCHAIN_RUNNER_PORT or 8000.
            **uvicorn_kwargs: Additional arguments passed to uvicorn.run().
        """
        import uvicorn

        from langchain_runner.server import create_app

        host = host or os.environ.get("LANGCHAIN_RUNNER_HOST", "0.0.0.0")
        port = port or int(os.environ.get("LANGCHAIN_RUNNER_PORT", "8000"))

        app = create_app(self)
        uvicorn.run(app, host=host, port=port, **uvicorn_kwargs)
