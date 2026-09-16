"""Schemas for staff attempt-monitoring reads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.attempts.models import AttemptEndReason, AttemptStatus


class AttemptMonitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    candidate_id: UUID
    admission_number: str
    candidate_name: str
    class_id: UUID
    status: AttemptStatus
    started_at: datetime
    ended_at: datetime | None
    end_reason: AttemptEndReason | None
    termination_reason: str | None
    time_limit_seconds: int
    remaining_seconds: int
    last_heartbeat_at: datetime
    last_activity_at: datetime


class AttemptMonitorListResponse(BaseModel):
    exam_id: UUID
    offset: int
    limit: int
    total: int
    attempts: list[AttemptMonitorResponse]
