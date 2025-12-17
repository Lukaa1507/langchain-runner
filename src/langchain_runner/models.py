"""Pydantic models for langchain-runner."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Status of an agent run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(str, Enum):
    """Type of trigger that initiated a run."""

    HTTP = "http"
    WEBHOOK = "webhook"
    CRON = "cron"


class Run(BaseModel):
    """Represents a single agent run."""

    run_id: str
    status: RunStatus = RunStatus.PENDING
    trigger_type: TriggerType
    trigger_name: str
    input: Any = None
    result: Any = None
    final_message: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunResponse(BaseModel):
    """Response when a run is created."""

    run_id: str
    status: RunStatus


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    agent_name: str | None = None


class TriggerInfo(BaseModel):
    """Information about a registered trigger."""

    name: str
    type: TriggerType
    path: str
    schedule: str | None = None  # For cron triggers
