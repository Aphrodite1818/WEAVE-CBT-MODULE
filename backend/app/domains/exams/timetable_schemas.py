from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BatchExamStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exam_ids: list[UUID] = Field(min_length=1)

    @field_validator("exam_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("exam_ids cannot contain duplicates")
        return value


class TimetableImpactResponse(BaseModel):
    exam_id: UUID
    title: str
    original_start_at: datetime
    proposed_start_at: datetime
    proposed_end_at: datetime


class BatchExamStartItemResponse(BaseModel):
    exam_id: UUID
    started: bool
    error: str | None = None
    impacts: list[TimetableImpactResponse] = Field(default_factory=list)


class BatchExamStartResponse(BaseModel):
    results: list[BatchExamStartItemResponse]
