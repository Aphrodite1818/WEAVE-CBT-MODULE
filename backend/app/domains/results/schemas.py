"""Response schemas for calculated examination results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.results.models import ResultSyncStatus


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    attempt_id: UUID
    candidate_id: UUID
    exam_id: UUID
    assessment_component_id: UUID
    raw_score: int
    raw_max_score: int
    percentage: Decimal
    component_score: Decimal
    component_maximum_score: Decimal
    calculated_at: datetime
    sync_status: ResultSyncStatus
    sync_batch_id: UUID | None
    sync_attempts: int
    last_sync_attempt_at: datetime | None
    synced_at: datetime | None
    sync_error: str | None


class ResultListResponse(BaseModel):
    exam_id: UUID
    offset: int
    limit: int
    total: int
    results: list[ResultResponse]


class ResultSyncRetryResponse(BaseModel):
    exam_id: UUID
    reset_count: int
    queued: bool
