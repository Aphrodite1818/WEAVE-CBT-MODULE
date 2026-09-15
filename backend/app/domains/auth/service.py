# =========================== #
#       auth/service.py       #
# =========================== #

"""Application service for local CBT staff authentication."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_local_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.settings import settings
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import (
    LocalActor,
    LocalActorSession,
    LocalRefreshToken,
)
from app.domains.auth.repository import AuthRepository
from app.domains.auth.schemas import StaffLoginRequest
from app.domains.node.identity_store import node_identity_store
from app.integrations.weave.auth import weave_auth_gateway
from app.integrations.weave.exceptions import WeaveContractError
from app.integrations.weave.schemas import WeaveStaffLoginRequest


INVALID_LOCAL_STAFF_SESSION = "Local staff session is invalid or expired."
SYNC_TRUST_REVOKED_REASON = "Weave staff authorization is no longer active."
REFRESH_REUSE_REASON = "Refresh token reuse detected."
LOGOUT_REASON = "Staff logged out."


class LocalSessionAuthenticationError(RuntimeError):
    """Raised when a local staff session or refresh token cannot be trusted."""


@dataclass(frozen=True)
class LocalLoginResult:
    """Internal result of a successful local staff login or refresh."""

    access_token: str
    refresh_token: str
    actor: LocalActor


class LocalAuthService:
    """Orchestrate local CBT authentication for Weave-authenticated staff."""

    @staticmethod
    async def login_staff(
        db: AsyncSession,
        *,
        payload: StaffLoginRequest,
    ) -> LocalLoginResult:
        """Authenticate through Weave, then establish a local CBT session.

        The Weave credential is used only for this fresh login. Once Weave has
        established the identity, normal CBT requests and local token refreshes
        use the local session and do not resend the password to Weave.
        """

        installation = node_identity_store.load()

        # Never hold a PostgreSQL transaction across the Cloud authentication
        # request. A school may have slow or intermittent internet connectivity.
        weave_actor = await weave_auth_gateway.authenticate_staff(
            payload=WeaveStaffLoginRequest(
                email=payload.email,
                password=payload.password,
            ),
            server_credential=installation.server_credential,
        )

        if weave_actor.tenant_id != installation.tenant_id:
            raise WeaveContractError(
                "Weave returned staff identity for an unexpected tenant"
            )

        if weave_actor.role == "teacher" and weave_actor.membership_id is None:
            raise WeaveContractError("Weave returned a teacher without a membership")

        if weave_actor.role == "admin" and weave_actor.membership_id is not None:
            raise WeaveContractError(
                "Weave returned an unexpected membership for an administrator"
            )

        now = datetime.now(UTC)
        session_expires_at = now + timedelta(
            hours=settings.LOCAL_REFRESH_TOKEN_EXPIRE_HOURS
        )

        async with db.begin():
            actor = await LocalAuthService._upsert_actor(
                db,
                weave_actor=weave_actor,
                now=now,
            )

            actor_session = LocalActorSession(
                actor_id=actor.id,
                expires_at=session_expires_at,
                last_seen_at=now,
            )
            actor_session = await AuthRepository.add_session(db, actor_session)

            raw_refresh_token = generate_refresh_token()
            refresh_token = LocalRefreshToken(
                session_id=actor_session.id,
                token_hash=hash_refresh_token(raw_refresh_token),
                expires_at=session_expires_at,
            )
            await AuthRepository.add_refresh_token(db, refresh_token)

            access_token = LocalAuthService._issue_access_token(
                actor=actor,
                session_id=actor_session.id,
                installation_id=installation.server_id,
                now=now,
            )

        return LocalLoginResult(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            actor=actor,
        )

    @staticmethod
    async def refresh_staff(
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> LocalLoginResult:
        """Rotate one local refresh token and issue a new access token.

        This is intentionally local-only. Refreshing an already-established CBT
        session never resends the staff member's Weave password.
        """

        if not refresh_token:
            raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)

        token_hash = hash_refresh_token(refresh_token)
        installation = node_identity_store.load()
        now = datetime.now(UTC)

        failure: str | None = None
        result: LocalLoginResult | None = None

        async with db.begin():
            # Resolve ownership without locks first, then acquire locks in the
            # stable actor -> session -> refresh-token order used by revocation.
            token_hint = await AuthRepository.get_refresh_token_by_hash(db, token_hash)
            if token_hint is None:
                raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)

            session_hint = await AuthRepository.get_session_by_id(
                db,
                token_hint.session_id,
            )
            if session_hint is None:
                raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)

            actor = await AuthRepository.get_actor_by_id(
                db,
                session_hint.actor_id,
                lock=True,
            )
            session = await AuthRepository.get_session_by_id(
                db,
                session_hint.id,
                lock=True,
            )
            stored_token = await AuthRepository.get_refresh_token_by_hash(
                db,
                token_hash,
                lock=True,
            )

            if (
                actor is None
                or session is None
                or stored_token is None
                or stored_token.session_id != session.id
                or session.actor_id != actor.id
            ):
                raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)

            if (
                not actor.is_active
                or session.revoked_at is not None
                or session.expires_at <= now
            ):
                if session.revoked_at is None:
                    await LocalAuthService._revoke_session_locked(
                        db,
                        session=session,
                        now=now,
                        reason=SYNC_TRUST_REVOKED_REASON,
                    )
                failure = INVALID_LOCAL_STAFF_SESSION

            elif stored_token.revoked_at is not None or stored_token.expires_at <= now:
                if stored_token.revoked_at is None:
                    stored_token.revoked_at = now
                    await AuthRepository.save_refresh_token(db, stored_token)
                failure = INVALID_LOCAL_STAFF_SESSION

            elif stored_token.consumed_at is not None:
                if stored_token.reuse_detected_at is None:
                    stored_token.reuse_detected_at = now
                    await AuthRepository.save_refresh_token(db, stored_token)
                await LocalAuthService._revoke_session_locked(
                    db,
                    session=session,
                    now=now,
                    reason=REFRESH_REUSE_REASON,
                )
                failure = INVALID_LOCAL_STAFF_SESSION

            else:
                replacement_raw_token = generate_refresh_token()
                replacement = LocalRefreshToken(
                    session_id=session.id,
                    token_hash=hash_refresh_token(replacement_raw_token),
                    # The 12-hour staff session is absolute, not sliding.
                    expires_at=session.expires_at,
                )
                replacement = await AuthRepository.add_refresh_token(db, replacement)

                stored_token.consumed_at = now
                stored_token.replaced_by_token_id = replacement.id
                await AuthRepository.save_refresh_token(db, stored_token)

                session.last_refreshed_at = now
                session.last_seen_at = now
                await AuthRepository.save_session(db, session)

                access_token = LocalAuthService._issue_access_token(
                    actor=actor,
                    session_id=session.id,
                    installation_id=installation.server_id,
                    now=now,
                )
                result = LocalLoginResult(
                    access_token=access_token,
                    refresh_token=replacement_raw_token,
                    actor=actor,
                )

        if failure is not None:
            raise LocalSessionAuthenticationError(failure)
        if result is None:
            raise LocalSessionAuthenticationError(INVALID_LOCAL_STAFF_SESSION)
        return result

    @staticmethod
    async def logout_staff(
        db: AsyncSession,
        *,
        refresh_token: str | None,
    ) -> None:
        """Revoke the local staff session represented by a refresh token."""

        if not refresh_token:
            return

        try:
            token_hash = hash_refresh_token(refresh_token)
        except ValueError:
            return

        now = datetime.now(UTC)

        async with db.begin():
            token_hint = await AuthRepository.get_refresh_token_by_hash(db, token_hash)
            if token_hint is None:
                return

            session_hint = await AuthRepository.get_session_by_id(
                db,
                token_hint.session_id,
            )
            if session_hint is None:
                stored_token = await AuthRepository.get_refresh_token_by_hash(
                    db,
                    token_hash,
                    lock=True,
                )
                if stored_token is not None and stored_token.revoked_at is None:
                    stored_token.revoked_at = now
                    await AuthRepository.save_refresh_token(db, stored_token)
                return

            actor = await AuthRepository.get_actor_by_id(
                db,
                session_hint.actor_id,
                lock=True,
            )
            session = await AuthRepository.get_session_by_id(
                db,
                session_hint.id,
                lock=True,
            )
            if session is None:
                return

            # Lock the presented token after actor/session locks so logout uses
            # the same ordering as refresh and synchronization revocation.
            stored_token = await AuthRepository.get_refresh_token_by_hash(
                db,
                token_hash,
                lock=True,
            )
            if stored_token is None or stored_token.session_id != session.id:
                return

            if actor is not None and session.actor_id != actor.id:
                return

            await LocalAuthService._revoke_session_locked(
                db,
                session=session,
                now=now,
                reason=LOGOUT_REASON,
            )

    @staticmethod
    async def reconcile_synced_staff_trust(
        db: AsyncSession,
        *,
        revalidated_at: datetime | None = None,
    ) -> None:
        """Remove local trust when the authoritative staff projection disappears.

        Weave projects only staff who are currently authorized for this CBT
        installation. Suspension/deactivation/removal therefore arrives as a
        teacher/admin tombstone (or absence from a full bootstrap).

        Synchronization may revoke trust, but it never silently reactivates a
        previously disabled LocalActor. Re-establishing trust requires a fresh
        successful Weave login.
        """

        checked_at = revalidated_at or datetime.now(UTC)
        actor_hints = await AuthRepository.list_actors(db, active_only=True)

        for actor_hint in actor_hints:
            actor = await AuthRepository.get_actor_by_id(
                db,
                actor_hint.id,
                lock=True,
            )
            if actor is None or not actor.is_active:
                continue

            trusted = await LocalAuthService._projection_trusts_actor(db, actor=actor)
            actor.last_weave_revalidated_at = checked_at

            if trusted:
                await AuthRepository.save_actor(db, actor)
                continue

            actor.is_active = False
            await AuthRepository.save_actor(db, actor)

            sessions = await AuthRepository.list_sessions_for_actor(
                db,
                actor.id,
                include_revoked=False,
                lock=True,
            )
            for session in sessions:
                await LocalAuthService._revoke_session_locked(
                    db,
                    session=session,
                    now=checked_at,
                    reason=SYNC_TRUST_REVOKED_REASON,
                )

    @staticmethod
    async def _projection_trusts_actor(
        db: AsyncSession,
        *,
        actor: LocalActor,
    ) -> bool:
        if actor.role == "admin":
            try:
                admin_id = UUID(actor.weave_actor_id)
            except (TypeError, ValueError):
                return False

            admin = await AcademicRepository.get_admin_by_id(db, admin_id)
            return admin is not None and str(admin.status).lower() == "active"

        if actor.role == "teacher":
            if actor.weave_membership_id is None:
                return False
            try:
                membership_id = UUID(actor.weave_membership_id)
            except (TypeError, ValueError):
                return False

            teacher = await AcademicRepository.get_teacher_by_membership_id(
                db,
                membership_id,
            )
            return bool(
                teacher is not None
                and str(teacher.status).lower() == "active"
                and str(teacher.teacher_account_id) == actor.weave_actor_id
            )

        return False

    @staticmethod
    async def _revoke_session_locked(
        db: AsyncSession,
        *,
        session: LocalActorSession,
        now: datetime,
        reason: str,
    ) -> None:
        """Revoke one locked session and every outstanding refresh token."""

        if session.revoked_at is None:
            session.revoked_at = now
            session.revocation_reason = reason
            await AuthRepository.save_session(db, session)

        refresh_tokens = await AuthRepository.list_refresh_tokens_for_session(
            db,
            session.id,
            include_revoked=False,
            lock=True,
        )
        changed: list[LocalRefreshToken] = []
        for token in refresh_tokens:
            if token.revoked_at is None:
                token.revoked_at = now
                changed.append(token)
        if changed:
            await AuthRepository.save_refresh_tokens(db, changed)

    @staticmethod
    def _issue_access_token(
        *,
        actor: LocalActor,
        session_id: UUID,
        installation_id: UUID,
        now: datetime,
    ) -> str:
        additional_claims: dict[str, str] = {}
        if actor.weave_membership_id is not None:
            additional_claims["membership_id"] = actor.weave_membership_id

        return create_local_access_token(
            subject=actor.weave_actor_id,
            session_id=str(session_id),
            role=actor.role,
            installation_id=str(installation_id),
            additional_claims=additional_claims,
            now=now,
        )

    @staticmethod
    async def _upsert_actor(
        db: AsyncSession,
        *,
        weave_actor,
        now: datetime,
    ) -> LocalActor:
        """Create or update the local projection of a Weave staff actor."""

        weave_actor_id = str(weave_actor.actor_id)
        weave_membership_id = (
            str(weave_actor.membership_id)
            if weave_actor.membership_id is not None
            else None
        )

        display_name = LocalAuthService._build_display_name(
            first_name=weave_actor.first_name,
            last_name=weave_actor.last_name,
            email=str(weave_actor.email),
        )

        actor = await AuthRepository.get_actor_by_weave_identity(
            db,
            weave_actor_id,
            weave_actor.role,
            lock=True,
        )

        if actor is None:
            actor = LocalActor(
                weave_actor_id=weave_actor_id,
                weave_membership_id=weave_membership_id,
                role=weave_actor.role,
                email=str(weave_actor.email),
                display_name=display_name,
                is_active=True,
                last_weave_authenticated_at=now,
                last_weave_revalidated_at=now,
            )
            return await AuthRepository.add_actor(db, actor)

        # Only a fresh successful Weave authentication may restore local trust.
        actor.weave_membership_id = weave_membership_id
        actor.email = str(weave_actor.email)
        actor.display_name = display_name
        actor.is_active = True
        actor.last_weave_authenticated_at = now
        actor.last_weave_revalidated_at = now
        return await AuthRepository.save_actor(db, actor)

    @staticmethod
    def _build_display_name(
        *,
        first_name: str | None,
        last_name: str | None,
        email: str,
    ) -> str:
        parts = [
            value.strip()
            for value in (
                first_name,
                last_name,
            )
            if value and value.strip()
        ]

        if parts:
            return " ".join(parts)

        return email
