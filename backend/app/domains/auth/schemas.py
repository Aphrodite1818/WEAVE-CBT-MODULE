# =========================== #
#       auth/schemas.py       #
# =========================== #

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffLoginRequest(BaseModel):
    """
    Credentials entered by a teacher/admin into the local CBT.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    email: EmailStr
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class LocalActorResponse(BaseModel):
    """
    Safe local actor representation returned to the frontend.
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: UUID
    role: Literal["admin", "teacher"]
    email: EmailStr
    display_name: str


class StaffLoginResponse(BaseModel):
    """
    Successful local CBT login.
    """

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    actor: LocalActorResponse