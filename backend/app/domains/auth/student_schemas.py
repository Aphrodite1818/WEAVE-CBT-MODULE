"""Schemas for local/offline student CBT authentication."""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentExamAvailability(str, PyEnum):
    READY = "ready"
    WAITING_FOR_ACTIVATION = "waiting_for_activation"
    MAKEUP = "makeup"


class StudentLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    admission_number: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class StudentLoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    student_id: UUID
    candidate_id: UUID
    exam_id: UUID
    exam_title: str
    display_name: str
    availability: StudentExamAvailability
    is_makeup: bool
    scheduled_start_at: datetime | None
    activated_at: datetime | None


class StudentSessionResponse(StudentLoginResponse):
    expires_at: datetime
