"""Resolve, validate, and refresh the local Weave branding projection."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.branding.models import BrandingState
from app.domains.branding.repository import BrandingRepository
from app.domains.branding.schemas import BrandingResponse
from app.domains.node.exceptions import NodeIdentityNotFoundError
from app.domains.node.identity_store import node_identity_store
from app.integrations.weave.branding import WeaveBrandingGateway, weave_branding_gateway

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_SCHEMA_VERSION = 4
DEFAULT_LIGHT_TOKENS: dict[str, str] = {
    "--color-primary": "29 78 216",
    "--color-primary-hover": "30 64 175",
    "--color-primary-soft": "239 246 255",
    "--color-primary-subtle": "248 250 252",
    "--color-primary-deep": "30 58 138",
    "--color-on-primary": "255 255 255",
    "--color-accent": "79 70 229",
    "--color-accent-hover": "67 56 202",
    "--color-accent-soft": "238 242 255",
    "--color-on-accent": "255 255 255",
    "--color-background": "248 250 252",
    "--color-surface": "255 255 255",
    "--color-surface-raised": "255 255 255",
    "--color-surface-muted": "248 250 252",
    "--color-surface-subtle": "241 245 249",
    "--color-border": "226 232 240",
    "--color-border-strong": "203 213 225",
    "--color-border-subtle": "241 245 249",
    "--color-text": "15 23 42",
    "--color-text-soft": "51 65 85",
    "--color-text-muted": "100 116 139",
    "--color-text-faint": "148 163 184",
    "--color-text-inverse": "255 255 255",
    "--color-sidebar-background": "255 255 255",
    "--color-sidebar-text": "15 23 42",
    "--color-sidebar-active": "29 78 216",
    "--color-sidebar-active-text": "255 255 255",
    "--color-sidebar-border": "226 232 240",
    "--color-header-background": "255 255 255",
    "--color-header-text": "15 23 42",
    "--color-header-text-muted": "100 116 139",
    "--color-header-surface": "248 250 252",
    "--color-header-surface-hover": "241 245 249",
    "--color-header-border": "226 232 240",
    "--color-focus-ring": "29 78 216",
}
SUPPORTED_LIGHT_TOKEN_KEYS = frozenset(DEFAULT_LIGHT_TOKENS)


class BrandingContractError(RuntimeError):
    """Raised when Weave branding cannot be safely projected into local CSS tokens."""


class BrandingService:
    def __init__(
        self,
        gateway: WeaveBrandingGateway = weave_branding_gateway,
    ) -> None:
        self.gateway = gateway

    @staticmethod
    def _normalize_channel_value(key: str, value: str) -> str:
        parts = str(value).strip().split()
        if len(parts) != 3:
            raise BrandingContractError(f"Invalid RGB branding token for {key}.")
        try:
            channels = tuple(int(part) for part in parts)
        except ValueError as exc:
            raise BrandingContractError(f"Invalid RGB branding token for {key}.") from exc
        if any(channel < 0 or channel > 255 for channel in channels):
            raise BrandingContractError(f"Invalid RGB branding token for {key}.")
        return " ".join(str(channel) for channel in channels)

    @classmethod
    def normalize_light_tokens(cls, tokens: dict[str, str]) -> dict[str, str]:
        """Overlay only known semantic tokens on top of the built-in Weave theme."""

        normalized = dict(DEFAULT_LIGHT_TOKENS)
        for key, value in tokens.items():
            if key not in SUPPORTED_LIGHT_TOKEN_KEYS:
                continue
            normalized[key] = cls._normalize_channel_value(key, value)
        return normalized

    @staticmethod
    def _default_response(
        *,
        tenant_id: UUID | None = None,
        school_name: str = "Weave CBT",
    ) -> BrandingResponse:
        return BrandingResponse(
            tenant_id=tenant_id,
            school_name=school_name,
            light_tokens=dict(DEFAULT_LIGHT_TOKENS),
            token_schema_version=DEFAULT_TOKEN_SCHEMA_VERSION,
            is_synced=False,
        )

    @staticmethod
    def _response_from_state(state: BrandingState) -> BrandingResponse:
        return BrandingResponse(
            tenant_id=state.tenant_id,
            school_name=state.school_name,
            logo_revision=state.logo_revision,
            is_enabled=state.is_enabled,
            is_default_theme=state.is_default_theme,
            theme_version=state.theme_version,
            token_schema_version=state.token_schema_version,
            light_tokens=dict(state.light_tokens),
            is_synced=True,
        )

    async def get_effective(self, db: AsyncSession) -> BrandingResponse:
        """Read local branding only; this endpoint never depends on Cloud availability."""

        try:
            identity = node_identity_store.load()
        except NodeIdentityNotFoundError:
            return self._default_response()

        state = await BrandingRepository.get_for_tenant(db, identity.tenant_id)
        if state is None:
            return self._default_response(
                tenant_id=identity.tenant_id,
                school_name=identity.tenant_name,
            )
        return self._response_from_state(state)

    async def refresh_from_weave(self, db: AsyncSession) -> BrandingResponse:
        """Fetch effective Weave branding and atomically replace the local projection."""

        identity = node_identity_store.load()
        projection = await self.gateway.fetch_branding(
            server_credential=identity.server_credential,
        )
        if projection.tenant_id != identity.tenant_id:
            raise BrandingContractError(
                "Weave branding belongs to an unexpected tenant."
            )

        light_tokens = self.normalize_light_tokens(projection.light_tokens)
        values = {
            "tenant_id": projection.tenant_id,
            "school_name": projection.school_name,
            "logo_url": projection.logo_url,
            "logo_revision": projection.logo_revision,
            "is_enabled": projection.is_enabled,
            "is_default_theme": projection.is_default_theme,
            "theme_version": projection.theme_version,
            "token_schema_version": projection.token_schema_version,
            "light_tokens": light_tokens,
            "last_synced_at": datetime.now(UTC),
        }

        await db.rollback()
        async with db.begin():
            state = await BrandingRepository.upsert(db, values=values)
        return self._response_from_state(state)

    async def refresh_best_effort(self, db: AsyncSession) -> bool:
        """Refresh branding without allowing an auxiliary theme failure to stop CBT work."""

        try:
            await self.refresh_from_weave(db)
            return True
        except NodeIdentityNotFoundError:
            await db.rollback()
            return False
        except Exception:
            await db.rollback()
            logger.warning(
                "Unable to refresh Weave tenant branding; keeping the last local theme.",
                exc_info=True,
            )
            return False


branding_service = BrandingService()
