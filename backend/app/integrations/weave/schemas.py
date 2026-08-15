# =======================================#
# backend.app.integrations.weave.schemas
# =======================================#


"""Schema contracts that would be used to pass request to weave client"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr , EmailStr
from typing import Literal


class WeavePairingRequest(BaseModel):
    """
    Payload sent by the local CBT Server to Weave Cloud
    during installatiion pairing
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    pairing_code: str = Field(..., min_length=8, max_length=20)
    server_name: str = Field(..., min_length=2, max_length=150)
    client_version: str | None = Field(default=None, max_length=50)


class WeaveTenantInfo(BaseModel):
    """
    Tenant identity returned by Weave after successful pairing
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str


class WeavePairingResult(BaseModel):
    """
    Successful pairing response returned by Weave Cloud

    server_credential is sensitive and must never be exposed
    to the CBT frontend
    """

    model_config = ConfigDict(extra="forbid")

    server_id: UUID
    server_credential: SecretStr
    server_name: str
    tenant: WeaveTenantInfo
    paired_at: datetime




class WeaveStaffLoginRequest(BaseModel):
    model_config = ConfigDict(
        extra = "forbid",
        str_strip_whitespace=True
    )

    email : EmailStr
    password : str


class WeaveStaffAuthResult(BaseModel):
    model_config = ConfigDict(
        frozen = True,
        extra ="forbid"
    )


    actor_id : UUID
    membership_id : UUID | None  = None
    tenant_id : UUID 

    role : Literal["admin", "teacher"]

    email : EmailStr
    first_name : str | None = None
    last_name : str | None = None
