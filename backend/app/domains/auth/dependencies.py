"""FastAPI dependencies for locally issued staff access tokens."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import DbSession
from app.core.security import InvalidLocalTokenError, decode_local_access_token
from app.domains.auth.models import LocalActor
from app.domains.auth.repository import AuthRepository
from app.domains.node.exceptions import NodeIdentityNotFoundError
from app.domains.node.identity_store import node_identity_store

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_local_actor(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> LocalActor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    try:
        payload = decode_local_access_token(credentials.credentials)
        session_id = UUID(str(payload["sid"]))
        identity = node_identity_store.load()
    except (InvalidLocalTokenError, ValueError, KeyError, NodeIdentityNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid local access token.") from exc

    if str(payload.get("installation_id")) != str(identity.server_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token belongs to another installation.")

    session = await AuthRepository.get_session_by_id(db, session_id)
    if session is None or session.revoked_at is not None or session.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Local session is not active.")

    actor = await AuthRepository.get_actor_by_id(db, session.actor_id)
    if actor is None or not actor.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Local actor is not active.")
    if actor.weave_actor_id != str(payload.get("sub")) or actor.role != payload.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token identity mismatch.")
    return actor


async def get_current_local_admin(
    actor: Annotated[LocalActor, Depends(get_current_local_actor)],
) -> LocalActor:
    """authorize local admin actors"""
    if actor.role not in {"admin", "tenant_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="School administrator access required.")
    return actor


async def get_current_local_teacher(
    actor : Annotated[LocalActor , Depends(get_current_local_actor)]
) -> LocalActor:
    """authorize local teacher actors """
    if actor.role !="teacher":
        raise HTTPException(
            status_code = 403,
            detail = "Teacher access required"
        )

    return actor



CurrentLocalActor = Annotated[LocalActor, Depends(get_current_local_actor)]
CurrentLocalAdmin = Annotated[LocalActor, Depends(get_current_local_admin)]
CurrentLocalTeacher = Annotated[LocalActor , Depends(get_current_local_teacher)]
