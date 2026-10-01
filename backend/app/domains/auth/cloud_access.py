"""On-demand repair of Weave actor authorization for cloud-backed CBT features."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    StoredSecretDecryptionError,
    decrypt_local_secret,
    encrypt_local_secret,
)
from app.domains.auth.coordination import staff_refresh_lock
from app.domains.auth.models import (
    WEAVE_AUTH_STATE_DEGRADED,
    WEAVE_AUTH_STATE_LEGACY,
    WEAVE_AUTH_STATE_REFRESH_PENDING,
    WEAVE_AUTH_STATE_REVOKED,
    WEAVE_AUTH_STATE_SYNCED,
)
from app.domains.auth.repository import AuthRepository
from app.domains.auth.service import (
    INVALID_LOCAL_STAFF_SESSION,
    WEAVE_AUTH_REJECTED_REASON,
    LocalAuthService,
    LocalSessionAuthenticationError,
)
from app.domains.node.identity_store import node_identity_store
from app.integrations.weave.auth import weave_auth_gateway
from app.integrations.weave.exceptions import WeaveRequestRejectedError, WeaveUnavailableError


async def get_or_repair_weave_actor_access_token(
    db: AsyncSession,
    *,
    session_id: UUID,
) -> str:
    """Return a usable actor token, repairing its Weave rotation when necessary."""

    try:
        return await LocalAuthService.get_weave_actor_access_token(
            db,
            session_id=session_id,
        )
    except LocalSessionAuthenticationError:
        pass

    async with staff_refresh_lock(session_id):
        try:
            return await LocalAuthService.get_weave_actor_access_token(
                db,
                session_id=session_id,
            )
        except LocalSessionAuthenticationError:
            pass

        operation_id, refresh_token = await _prepare_cloud_repair(
            db,
            session_id=session_id,
        )
        installation = node_identity_store.load()

        try:
            token_pair = await weave_auth_gateway.refresh_staff_authorization(
                refresh_token=refresh_token,
                idempotency_key=operation_id,
                server_credential=installation.server_credential,
            )
        except WeaveUnavailableError:
            await _mark_cloud_repair_degraded(
                db,
                session_id=session_id,
                operation_id=operation_id,
            )
            raise
        except WeaveRequestRejectedError as exc:
            if exc.status_code in {401, 403}:
                await _revoke_cloud_session(
                    db,
                    session_id=session_id,
                    reason=WEAVE_AUTH_REJECTED_REASON,
                )
            else:
                await _mark_cloud_repair_degraded(
                    db,
                    session_id=session_id,
                    operation_id=operation_id,
                )
            raise

        return await _complete_cloud_repair(
            db,
            session_id=session_id,
            operation_id=operation_id,
            token_pair=token_pair,
        )


async def _prepare_cloud_repair(
    db: AsyncSession,
    *,
    session_id: UUID,
) -> tuple[UUID, str]:
    now = datetime.now(UTC)
    operation_id: UUID | None = None
    refresh_token: str | None = None

    async with db.begin():
        session = await AuthRepository.get_session_by_id(db, session_id, lock=True)
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= now
            or session.weave_auth_state in {WEAVE_AUTH_STATE_LEGACY, WEAVE_AUTH_STATE_REVOKED}
            or session.weave_refresh_token_encrypted is None
            or session.weave_refresh_token_expires_at is None
            or session.weave_refresh_token_expires_at <= now
        ):
            raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)

        operation_id = session.weave_refresh_operation_id or uuid4()
        session.weave_refresh_operation_id = operation_id
        session.weave_auth_state = WEAVE_AUTH_STATE_REFRESH_PENDING
        await AuthRepository.save_session(db, session)

        try:
            refresh_token = decrypt_local_secret(
                session.weave_refresh_token_encrypted,
                purpose=LocalAuthService._weave_refresh_purpose(session.id),
            )
        except StoredSecretDecryptionError as exc:
            await LocalAuthService._revoke_session_locked(
                db,
                session=session,
                now=now,
                reason=WEAVE_AUTH_REJECTED_REASON,
            )
            raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION) from exc

    if operation_id is None or refresh_token is None:
        raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)
    return operation_id, refresh_token


async def _complete_cloud_repair(
    db: AsyncSession,
    *,
    session_id: UUID,
    operation_id: UUID,
    token_pair,
) -> str:
    now = datetime.now(UTC)
    access_expiry, refresh_expiry = LocalAuthService._validate_token_pair_times(
        access_expires_at=token_pair.access_token_expires_at,
        refresh_expires_at=token_pair.refresh_token_expires_at,
        now=now,
    )

    async with db.begin():
        session = await AuthRepository.get_session_by_id(db, session_id, lock=True)
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= now
            or session.weave_refresh_operation_id != operation_id
        ):
            raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)

        if refresh_expiry > session.expires_at + timedelta(seconds=2):
            raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)
        if refresh_expiry < session.expires_at:
            session.expires_at = refresh_expiry

        raw_access_token = token_pair.access_token.get_secret_value()
        session.weave_access_token_encrypted = encrypt_local_secret(
            raw_access_token,
            purpose=LocalAuthService._weave_access_purpose(session.id),
        )
        session.weave_access_token_issued_at = now
        session.weave_access_token_expires_at = min(access_expiry, session.expires_at)
        session.weave_refresh_token_encrypted = encrypt_local_secret(
            token_pair.refresh_token.get_secret_value(),
            purpose=LocalAuthService._weave_refresh_purpose(session.id),
        )
        session.weave_refresh_token_expires_at = min(
            refresh_expiry,
            session.expires_at,
        )
        session.weave_refresh_operation_id = None
        session.weave_auth_state = WEAVE_AUTH_STATE_SYNCED
        await AuthRepository.save_session(db, session)

    return raw_access_token


async def _mark_cloud_repair_degraded(
    db: AsyncSession,
    *,
    session_id: UUID,
    operation_id: UUID,
) -> None:
    async with db.begin():
        session = await AuthRepository.get_session_by_id(db, session_id, lock=True)
        if (
            session is not None
            and session.revoked_at is None
            and session.weave_refresh_operation_id == operation_id
        ):
            session.weave_auth_state = WEAVE_AUTH_STATE_DEGRADED
            await AuthRepository.save_session(db, session)


async def _revoke_cloud_session(
    db: AsyncSession,
    *,
    session_id: UUID,
    reason: str,
) -> None:
    now = datetime.now(UTC)
    async with db.begin():
        session = await AuthRepository.get_session_by_id(db, session_id, lock=True)
        if session is not None:
            await LocalAuthService._revoke_session_locked(
                db,
                session=session,
                now=now,
                reason=reason,
            )
