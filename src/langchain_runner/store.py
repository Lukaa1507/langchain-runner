"""In-memory run store for langchain-runner."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from langchain_runner.models import Run, RunStatus, TriggerType


class RunStore:
    """In-memory store for tracking agent runs.

    Uses an OrderedDict with a max size to prevent unbounded memory growth.
    Oldest runs are evicted when the limit is reached.
    """

    def __init__(self, max_runs: int = 1000) -> None:
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._max_runs = max_runs

    def create_run(
        self,
        trigger_type: TriggerType,
        trigger_name: str,
        input: Any = None,
    ) -> Run:
        """Create a new run and return it."""
        run_id = str(uuid.uuid4())[:8]  # Short ID for readability

        run = Run(
            run_id=run_id,
            status=RunStatus.PENDING,
            trigger_type=trigger_type,
            trigger_name=trigger_name,
            input=input,
            created_at=datetime.now(UTC),
        )

        # Evict oldest if at capacity
        while len(self._runs) >= self._max_runs:
            self._runs.popitem(last=False)

        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> Run | None:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 50) -> list[Run]:
        """List recent runs, most recent first."""
        runs = list(self._runs.values())
        runs.reverse()  # Most recent first
        return runs[:limit]

    def update_run(
        self,
        run_id: str,
        status: RunStatus | None = None,
        result: Any = None,
        final_message: str | None = None,
        error: str | None = None,
    ) -> Run | None:
        """Update a run's status and result."""
        run = self._runs.get(run_id)
        if not run:
            return None

        if status is not None:
            run.status = status

        if status == RunStatus.RUNNING:
            run.started_at = datetime.now(UTC)

        if status in (RunStatus.COMPLETED, RunStatus.FAILED):
            run.completed_at = datetime.now(UTC)

        if result is not None:
            run.result = result

        if final_message is not None:
            run.final_message = final_message

        if error is not None:
            run.error = error

        return run
