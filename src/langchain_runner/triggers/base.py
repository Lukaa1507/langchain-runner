"""Trigger classes for langchain-runner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from langchain_runner.models import TriggerType


@dataclass
class Trigger:
    """A trigger that invokes an agent."""

    name: str
    handler: Callable[..., Coroutine[Any, Any, str | dict] | str | dict]
    trigger_type: TriggerType
    schedule: str | None = None  # Only for cron triggers

    @property
    def path(self) -> str:
        """Get the API path for this trigger."""
        prefix = "trigger" if self.trigger_type == TriggerType.HTTP else self.trigger_type.value
        return f"/{prefix}/{self.name}"

    async def get_input(self, **kwargs: Any) -> str | dict:
        """Execute the handler to get the agent input."""
        result = self.handler(**kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
