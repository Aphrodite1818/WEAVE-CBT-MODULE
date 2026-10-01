"""Question-authoring extension over the existing CBT -> Weave AI gateway."""

from __future__ import annotations

import asyncio

from pydantic import SecretStr, ValidationError

from app.integrations.weave.ai import AI_PATH, WeaveAIGateway, weave_ai_gateway
from app.integrations.weave.ai_authoring_schemas import (
    AIGenerateQuestionsRequest,
    AIGenerateQuestionsResponse,
    AIRegenerateQuestionRequest,
    AIRegenerateQuestionResponse,
)
from app.integrations.weave.exceptions import (
    WeaveContractError,
    WeaveUnavailableError,
)


class WeaveAIQuestionAuthoringGateway:
    """Add authoring calls while reusing the shared AI gateway/client/auth stack."""

    def __init__(self, gateway: WeaveAIGateway = weave_ai_gateway) -> None:
        self.gateway = gateway

    async def generate_questions(
        self,
        *,
        payload: AIGenerateQuestionsRequest,
        idempotency_key: str,
        server_credential: SecretStr,
        actor_access_token: str,
    ) -> AIGenerateQuestionsResponse:
        raw = await self._request_with_transport_retry(
            path="/questions/generate",
            payload=payload.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            server_credential=server_credential,
            actor_access_token=actor_access_token,
        )
        try:
            return AIGenerateQuestionsResponse.model_validate(raw)
        except ValidationError as exc:
            raise WeaveContractError(
                "Weave returned an invalid CBT AI generation response."
            ) from exc

    async def regenerate_question(
        self,
        *,
        payload: AIRegenerateQuestionRequest,
        idempotency_key: str,
        server_credential: SecretStr,
        actor_access_token: str,
    ) -> AIRegenerateQuestionResponse:
        raw = await self._request_with_transport_retry(
            path="/questions/regenerate",
            payload=payload.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            server_credential=server_credential,
            actor_access_token=actor_access_token,
        )
        try:
            return AIRegenerateQuestionResponse.model_validate(raw)
        except ValidationError as exc:
            raise WeaveContractError(
                "Weave returned an invalid CBT AI regeneration response."
            ) from exc

    async def _request_with_transport_retry(
        self,
        *,
        path: str,
        payload: dict,
        idempotency_key: str,
        server_credential: SecretStr,
        actor_access_token: str,
    ) -> dict:
        """Retry one ambiguous transport failure with exactly the same key."""

        for attempt in range(2):
            try:
                return await self.gateway.client.request_actor_authenticated(
                    "POST",
                    f"{AI_PATH}{path}",
                    server_credential=server_credential,
                    actor_access_token=actor_access_token,
                    json=payload,
                    headers={"Idempotency-Key": idempotency_key},
                )
            except WeaveUnavailableError:
                if attempt:
                    raise
                await asyncio.sleep(0.2)
        raise RuntimeError("Unreachable AI authoring retry state")


weave_ai_question_authoring_gateway = WeaveAIQuestionAuthoringGateway()
