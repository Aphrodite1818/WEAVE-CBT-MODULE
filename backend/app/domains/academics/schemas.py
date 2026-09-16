from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel , ConfigDict


class InputBase(BaseModel):
    pass


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )


class AcademicSessionResponse(OutputBase):
    """carries academic session context"""
    id : UUID
    name : str
    status : str
    is_current : bool
    synced_at : datetime


class AcademicTermResponse(OutputBase):
    """carries academic term context"""
    id : UUID
    name : str
    status : str
    is_current : bool
    synced_at : datetime


class AuthorableCurriculumSubjectResponse(OutputBase):
    id : UUID
    curriculum_id : UUID

    subject_id : UUID
    subject_name : str
    subject_code : str | None

    is_elective: bool
    is_active  : bool