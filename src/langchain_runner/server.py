"""FastAPI server for langchain-runner."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from langchain_runner import __version__
from langchain_runner.models import (
    HealthResponse,
    Run,
    RunResponse,
    RunStatus,
    TriggerInfo,
    TriggerType,
)
from langchain_runner.triggers import Trigger

if TYPE_CHECKING:
    from langchain_runner.runner import Runner


def create_app(runner: Runner) -> FastAPI:
    """Create a FastAPI application for the runner.

    Args:
        runner: The Runner instance to serve.

    Returns:
        A configured FastAPI application.
    """
    scheduler = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage scheduler lifecycle."""
        nonlocal scheduler

        # Start cron scheduler if there are cron triggers
        cron_triggers = runner.get_cron_triggers()
        if cron_triggers:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger as APSCronTrigger

            scheduler = AsyncIOScheduler()

            for trigger in cron_triggers:
                async def job(t=trigger):
                    input_msg = await t.get_input()
                    await runner.run_agent(t, input_msg)

                scheduler.add_job(
                    job,
                    APSCronTrigger.from_crontab(trigger.schedule),
                    id=trigger.name,
                    name=trigger.name,
                )

            scheduler.start()

        yield

        # Shutdown scheduler
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(
        title="langchain-runner",
        description="LangChain/LangGraph agent runner",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=__version__,
            agent_name=runner.name,
        )

    @app.get("/triggers", response_model=list[TriggerInfo])
    async def list_triggers() -> list[TriggerInfo]:
        """List all registered triggers."""
        triggers = runner.get_triggers()
        return [
            TriggerInfo(
                name=t.name,
                type=t.trigger_type,
                path=t.path,
                schedule=t.schedule,
            )
            for t in triggers
        ]

    @app.get("/runs", response_model=list[Run])
    async def list_runs(limit: int = 50) -> list[Run]:
        """List recent runs."""
        return runner.store.list_runs(limit=limit)

    @app.get("/runs/{run_id}", response_model=Run)
    async def get_run(run_id: str) -> Run:
        """Get a specific run by ID."""
        run = runner.store.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return run

    async def _invoke(
        name: str,
        expected_type: TriggerType,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> RunResponse:
        """Shared handler for trigger/webhook invocation."""
        trigger = runner._triggers.get(name)
        if not trigger:
            raise HTTPException(status_code=404, detail=f"Trigger '{name}' not found")

        if trigger.trigger_type != expected_type:
            raise HTTPException(
                status_code=400,
                detail=f"Trigger '{name}' is not a {expected_type.value} trigger",
            )

        # Parse request body
        try:
            body = await request.json()
        except Exception:
            body = {}

        # Build kwargs for handler
        if expected_type == TriggerType.WEBHOOK:
            # Webhooks get the entire body as "payload"
            kwargs = {"payload": body}
        else:
            # HTTP triggers get individual params from body
            sig = inspect.signature(trigger.handler)
            kwargs = {k: body.get(k) for k in sig.parameters if k in body}

        # Get input from handler
        input_msg = await trigger.get_input(**kwargs)

        # Create run record and execute in background
        run = runner.store.create_run(
            trigger_type=expected_type,
            trigger_name=name,
            input=input_msg,
        )
        background_tasks.add_task(runner._execute_run, run.run_id, input_msg)

        return RunResponse(run_id=run.run_id, status=RunStatus.PENDING)

    @app.post("/trigger/{name}", response_model=RunResponse)
    async def invoke_trigger(
        name: str, request: Request, background_tasks: BackgroundTasks
    ) -> RunResponse:
        """Invoke a registered HTTP trigger."""
        return await _invoke(name, TriggerType.HTTP, request, background_tasks)

    @app.post("/webhook/{name}", response_model=RunResponse)
    async def invoke_webhook(
        name: str, request: Request, background_tasks: BackgroundTasks
    ) -> RunResponse:
        """Receive a webhook and invoke the agent."""
        return await _invoke(name, TriggerType.WEBHOOK, request, background_tasks)

    return app
