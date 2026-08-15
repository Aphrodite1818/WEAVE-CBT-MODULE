# =====================================#
# backend.app.integrations.weave.client
# =====================================#

"""This file handles Weave requests and Weave requests alone."""

from typing import Any

import httpx
from pydantic import SecretStr

from app.core.settings import settings
from app.integrations.weave.exceptions import (
    WeaveContractError,
    WeaveRequestRejectedError,
    WeaveUnavailableError,
)


class WeaveClient:
    """
    Low-level HTTP client for communication with Weave Cloud.

    This layer owns network mechanics only.

    Domain-specific operations such as installation pairing,
    staff authentication, academic synchronization, and result
    synchronization belong in their respective Weave integration modules.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (
            base_url or str(settings.WEAVE_API_BASE_URL)
        ).rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Send an HTTP request to Weave Cloud.

        Owns transport-level concerns only:
        - URL construction
        - timeout handling
        - network failure mapping
        - rejected request mapping
        - JSON object parsing
        """

        url = self._build_url_path(path)

        timeout = httpx.Timeout(
            timeout=settings.WEAVE_REQUEST_TIMEOUT_SECONDS,
            connect=settings.WEAVE_CONNECT_TIMEOUT_SECONDS,
        )

        request_headers = {
            "Accept": "application/json",
        }

        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    headers=request_headers,
                )

        except httpx.TimeoutException as exc:
            raise WeaveUnavailableError(
                "Weave Cloud did not respond in time"
            ) from exc

        except httpx.RequestError as exc:
            raise WeaveUnavailableError(
                "Unable to connect to Weave Cloud"
            ) from exc

        if not response.is_success:
            raise WeaveRequestRejectedError(
                status_code=response.status_code,
                detail=self._extract_error_detail(response),
                retry_after=self._extract_retry_after(response),
            )

        return self._parse_json_object(response)

    async def post_public(
        self,
        *,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send an unauthenticated POST request to Weave Cloud.

        Used for bootstrap operations such as installation pairing
        where the CBT server does not yet possess a machine credential.
        """

        return await self._request(
            "POST",
            path,
            json=payload,
        )

    async def request_authenticated(
        self,
        method: str,
        path: str,
        *,
        server_credential: SecretStr,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send a machine-authenticated request to Weave Cloud.
        """

        return await self._request(
            method,
            path,
            json=json,
            headers={
                "Authorization": (
                    f"Bearer {server_credential.get_secret_value()}"
                )
            },
        )

    def _build_url_path(self, path: str) -> str:
        """
        Build an absolute Weave API URL from a relative API path.
        """

        normalized_path = "/" + path.lstrip("/")

        return f"{self.base_url}{normalized_path}"

    @staticmethod
    def _parse_json_object(
        response: httpx.Response,
    ) -> dict[str, Any]:
        """
        Parse a successful Weave response as a JSON object.

        Domain-specific schema validation happens in the integration
        module responsible for that operation.
        """

        try:
            payload = response.json()

        except ValueError as exc:
            raise WeaveContractError(
                "Weave returned an invalid JSON response."
            ) from exc

        if not isinstance(payload, dict):
            raise WeaveContractError(
                "Weave returned an unexpected response structure."
            )

        return payload

    @staticmethod
    def _extract_error_detail(
        response: httpx.Response,
    ) -> str:
        """
        Safely extract a human-readable error message from a rejected
        Weave request.

        Raw response bodies are deliberately not propagated.
        """

        try:
            payload = response.json()

        except ValueError:
            return "Weave rejected the request."

        if not isinstance(payload, dict):
            return "Weave rejected the request."

        detail = payload.get("detail")

        if isinstance(detail, str) and detail.strip():
            return detail.strip()

        return "Weave rejected the request."

    @staticmethod
    def _extract_retry_after(
        response: httpx.Response,
    ) -> int | None:
        """
        Return Retry-After in seconds when Weave provides a numeric value.
        """

        value = response.headers.get("Retry-After")

        if value is None:
            return None

        value = value.strip()

        if not value.isdigit():
            return None

        return int(value)


weave_client = WeaveClient()