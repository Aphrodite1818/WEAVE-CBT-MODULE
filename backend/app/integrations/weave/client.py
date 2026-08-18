"""Low-level HTTP transport for communication with Weave Cloud."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import SecretStr

from app.core.settings import settings
from app.integrations.weave.exceptions import (
    WeaveContractError,
    WeaveRequestRejectedError,
    WeaveUnavailableError,
)


class WeaveClient:
    """Own transport mechanics only; domain-specific contracts live elsewhere."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or str(settings.WEAVE_API_BASE_URL)).rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = self._build_url_path(path)
        timeout = httpx.Timeout(
            timeout=settings.WEAVE_REQUEST_TIMEOUT_SECONDS,
            connect=settings.WEAVE_CONNECT_TIMEOUT_SECONDS,
        )
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=request_headers,
                )
        except httpx.TimeoutException as exc:
            raise WeaveUnavailableError("Weave Cloud did not respond in time") from exc
        except httpx.RequestError as exc:
            raise WeaveUnavailableError("Unable to connect to Weave Cloud") from exc

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
        return await self._request("POST", path, json=payload)

    async def request_authenticated(
        self,
        method: str,
        path: str,
        *,
        server_credential: SecretStr,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            method,
            path,
            json=json,
            params=params,
            headers={
                "Authorization": f"Bearer {server_credential.get_secret_value()}"
            },
        )

    def _build_url_path(self, path: str) -> str:
        return f"{self.base_url}/" + path.lstrip("/")

    def build_websocket_url(self, path: str) -> str:
        """Build the authenticated Weave WebSocket endpoint from the HTTP base URL."""
        parsed = urlsplit(self._build_url_path(path))
        if parsed.scheme == "https":
            scheme = "wss"
        elif parsed.scheme == "http":
            scheme = "ws"
        else:
            raise WeaveContractError("WEAVE_API_BASE_URL must use http or https.")
        return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))

    @staticmethod
    def _parse_json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeaveContractError("Weave returned an invalid JSON response.") from exc
        if not isinstance(payload, dict):
            raise WeaveContractError("Weave returned an unexpected response structure.")
        return payload

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
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
    def _extract_retry_after(response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        value = value.strip()
        return int(value) if value.isdigit() else None


weave_client = WeaveClient()
