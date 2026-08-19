# ===============================================#
# backend.app.core.domains.questions.schemas.py
# ===============================================#


from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.domains.questions.models import QuestionType


class InputBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class QuestionBankCreate(InputBase):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class QuestionBankResponse(OutputBase):
    id: UUID
    curriculum_subject_id: UUID
    name: str
    description: str | None
    created_by_actor_id: UUID
    is_active: bool


class QuestionOptionCreate(InputBase):
    """schema for creating options for a question
    and also marking the correct option
    """

    text: str = Field(min_length=1)
    is_correct: bool = False


class SingleChoiceQuestionCreate(InputBase):
    """
    schema for creating questions

    Types:
        single_choice
        multi-choice
    """

    prompt: str = Field(min_length=1)
    instruction: str | None = None
    image_asset_id: UUID | None = None

    options: list[QuestionOptionCreate] = Field(min_length=2)


class QuestionOptionResponse(OutputBase):
    id: UUID
    question_id: UUID
    position: int
    text: str
    is_correct: bool


class QuestionRead(OutputBase):
    id: UUID
    bank_id: UUID
    question_type: QuestionType
    prompt: str
    instruction: str | None
    image_url: str | None
    version: int
    created_by_actor_id: UUID
    last_edited_by_actor_id: UUID | None
    is_active: bool


class MultipleChoiceQuestionCreate(InputBase):
    prompt: str = Field(min_length=1)
    instruction: str | None = None
    image_asset_id: UUID | None = None
    options: list[QuestionOptionCreate] = Field(min_length=2)


class QuestionUpdate(InputBase):
    """
     model_fields_set lets the service distinguish:

    image_asset_id omitted
        -> keep existing image

    image_asset_id=None
        -> remove existing image

    image_asset_id=<uuid>
        -> replace existing image
    """

    prompt: str | None = None
    instruction: str | None = None
    image_asset_id: UUID | None = None
    options: list[QuestionOptionCreate] | None = None


class QuestionBankUpdate(InputBase):
    name: str | None = None
    description: str | None = None
    curriculum_subject_id: UUID | None = None
