# ==================================== #
# app.integrations.weave.auth
# ==================================== #

"""Weave Cloud staff authentication integration."""

from pydantic import SecretStr, ValidationError

from app.integrations.weave.client import (
    WeaveClient,
    weave_client,
)
from app.integrations.weave.exceptions import WeaveContractError
from app.integrations.weave.schemas import (
    WeaveStaffAuthResult,
    WeaveStaffLoginRequest,
)


class WeaveAuthGateway:
    """
    Domain-specific gateway for staff authentication against Weave Cloud.

    Network mechanics belong to WeaveClient.
    """

    def __init__(
        self,
        client: WeaveClient,
    ) -> None:
        self.client = client

    async def authenticate_staff(
        self,
        *,
        payload: WeaveStaffLoginRequest,
        server_credential: SecretStr,
    ) -> WeaveStaffAuthResult:
        """
        Authenticate a tenant admin or teacher through Weave Cloud.
        """

        response = await self.client.request_authenticated(
            "POST",
            "/api/v1/cbt/auth/staff/login",
            server_credential=server_credential,
            json=payload.model_dump(
                mode="json",
            ),
        )

        try:
            return WeaveStaffAuthResult.model_validate(response)

        except ValidationError as exc:
            raise WeaveContractError(
                "Weave returned an invalid staff authentication response."
            ) from exc


weave_auth_gateway = WeaveAuthGateway(
    client=weave_client,
)
