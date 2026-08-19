# =========================== #
#       auth/service.py       #
# =========================== #

"""Application service for local CBT staff authentication."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_local_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.settings import settings
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


@dataclass(frozen=True)
class LocalLoginResult:
    """
    Internal result of a successful local staff login

    The raw refresh token exists only long enough for the HTTP
    route to place it into an HttpOnly cookie
    """

    access_token: str
    refresh_token: str
    actor: LocalActor


class LocalAuthService:
    """
    Orchestration local CBT authentication for Weave-authenticated staff
    """

    @staticmethod
    async def login_staff(db: AsyncSession, *, payload: StaffLoginRequest):
        """
        Authenticate staff through Weave , project the actor locally,
        and create an independent local CBT session
        """

        installation = node_identity_store.load()

        # Authenticate the huan against Weave Cloud
        # IMPORTANT
        # Do this before opening a database transaction
        # Never hold a PostgreSQL transaction accross a
        # potentially slow network request

        weave_actor = await weave_auth_gateway.authenticate_staff(
            payload=WeaveStaffLoginRequest(
                email=payload.email, password=payload.password
            ),
            server_credential=installation.server_credential,
        )

        # extra checks
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
                db, weave_actor=weave_actor, now=now
            )

            actor_session = LocalActorSession(
                actor_id=actor.id, expires_at=session_expires_at, last_seen_at=now
            )

            actor_session = await AuthRepository.add_session(db, actor_session)

            raw_refresh_token = generate_refresh_token()

            refresh_token = LocalRefreshToken(
                session_id=actor_session.id,
                token_hash=hash_refresh_token(raw_refresh_token),
                expires_at=session_expires_at,
            )

            await AuthRepository.add_refresh_token(db, refresh_token)

            additional_claims: dict[str, str] = {}

            if actor.weave_membership_id is not None:
                additional_claims["membership_id"] = actor.weave_membership_id

            access_token = create_local_access_token(
                subject=actor.weave_actor_id,
                session_id=str(actor_session.id),
                role=actor.role,
                installation_id=str(installation.server_id),
                additional_claims=additional_claims,
                now=now,
            )

        return LocalLoginResult(
            access_token=access_token, refresh_token=raw_refresh_token, actor=actor
        )

    @staticmethod
    async def _upsert_actor(db: AsyncSession, *, weave_actor, now: datetime):
        """
        Create or update the local projection of a Weave staff actor
        """

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
            db, weave_actor_id, weave_actor.role, lock=True
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

            return await AuthRepository.add_actor(
                db,
                actor,
            )

        actor.weave_membership_id = weave_membership_id
        actor.email = str(weave_actor.email)
        actor.display_name = display_name
        actor.is_active = True

        actor.last_weave_authenticated_at = now
        actor.last_weave_revalidated_at = now

        return await AuthRepository.save_actor(
            db,
            actor,
        )

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
