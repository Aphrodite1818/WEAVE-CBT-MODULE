from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.candidates.models import CandidateStatus
from app.domains.exams.models import ExamRosterStatus


class InputBase(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        extra="forbid",
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )


class CandidateStatusReasonPayload(InputBase):
    reason: str = Field(min_length=1, max_length=500)


class CandidateLateStartGrantPayload(InputBase):
    reason: str = Field(min_length=1)
    expires_at: datetime | None = None


class CandidateLateStartRevocationPayload(InputBase):
    reason: str = Field(min_length=1)


class CandidateMakeupApprovalPayload(InputBase):
    reason: str = Field(
        min_length=1,
        max_length=500,
    )


class CandidateMakeupRevocationPayload(InputBase):
    reason: str = Field(
        min_length=1,
        max_length=500,
    )


class CandidateResponse(OutputBase):
    id: UUID

    exam_id: UUID
    enrollment_id: UUID
    student_id: UUID
    class_id: UUID
    class_name: str | None = None

    admission_number: str
    display_name: str

    status: CandidateStatus
    status_reason: str | None

    roster_version: int

    created_at: datetime
    updated_at: datetime


class CandidateRosterClassResponse(OutputBase):
    id: UUID
    display_name: str


class CandidateRosterResponse(OutputBase):
    exam_id: UUID

    roster_status: ExamRosterStatus
    roster_version: int

    roster_candidate_count: int

    offset: int
    limit: int
    total: int

    classes: list[CandidateRosterClassResponse] = Field(default_factory=list)
    candidates: list[CandidateResponse]


class CandidateRosterRetryResponse(OutputBase):
    exam_id: UUID
    roster_status: ExamRosterStatus
    roster_version: int
    recovery_mode: Literal["prepare", "reconcile"]
    queued: bool


class CandidateMakeupAuthorizationResponse(OutputBase):
    id: UUID
    candidate_id: UUID

    approved_by_actor_id: UUID
    reason: str
    approved_at: datetime

    consumed_at: datetime | None

    revoked_at: datetime | None
    revoked_by_actor_id: UUID | None
    revocation_reason: str | None

    created_at: datetime
    updated_at: datetime


class MissedCandidateResponse(OutputBase):
    candidate: CandidateResponse
    makeup_authorization: CandidateMakeupAuthorizationResponse | None


class MissedCandidateListResponse(OutputBase):
    exam_id: UUID
    exam_title: str
    scheduled_start_at: datetime | None

    offset: int
    limit: int
    total: int

    candidates: list[MissedCandidateResponse]


class CandidateLateStartAuthorizationResponse(OutputBase):
    id: UUID
    candidate_id: UUID
    granted_by_actor_id: UUID
    reason: str
    granted_at: datetime
    expires_at: datetime | None
    consumed_at: datetime | None
    revoked_at: datetime | None
    revoked_by_actor_id: UUID | None
    revocation_reason: str | None
    created_at: datetime
    updated_at: datetime
