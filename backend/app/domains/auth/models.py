# =========================== #
#        auth/models.py       #
# =========================== #

"""Database models for local teacher and administrator authentication."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

WEAVE_ID_MAX_LENGTH = 128
ACTOR_ROLE_MAX_LENGTH = 64
ACTOR_EMAIL_MAX_LENGTH = 255
ACTOR_NAME_MAX_LENGTH = 255
REFRESH_TOKEN_HASH_LENGTH = 64
REVOCATION_REASON_MAX_LENGTH = 500


class LocalActor(Base):
    """
    Local representation of a teacher or tenant administrator authenticated
    through Weave.

    The CBT never stores the actor's Weave password.

    After Weave successfully authenticates the user, the local CBT stores only
    the identity information needed for local authorization and session
    management.
    """

    __tablename__ = "local_actors"

    weave_actor_id: Mapped[str] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=False,
    )

    weave_membership_id: Mapped[str | None] = mapped_column(
        String(WEAVE_ID_MAX_LENGTH),
        nullable=True,
        unique=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(ACTOR_ROLE_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(ACTOR_EMAIL_MAX_LENGTH),
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(ACTOR_NAME_MAX_LENGTH),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    last_weave_authenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


    last_weave_revalidated_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "weave_actor_id",
            "role",
            name="uq_local_actors_weave_actor_role",
        ),
        CheckConstraint(
            "char_length(trim(role)) > 0",
            name="ck_local_actors_role_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(email)) > 0",
            name="ck_local_actors_email_not_blank",
        ),
        Index(
            "ix_local_actors_role_active",
            "role",
            "is_active",
        ),
    )


class LocalActorSession(Base):
    """
    One local login session belonging to a LocalActor.

    The database row ID is used as the JWT `sid` claim.

    Access tokens are short-lived JWTs and are not stored in the database.

    Refresh-token rotation, revocation, and reuse detection are handled through
    LocalRefreshToken rows belonging to this session.
    """

    __tablename__ = "local_actor_sessions"

    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "local_actors.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    revocation_reason: Mapped[str | None] = mapped_column(
        String(REVOCATION_REASON_MAX_LENGTH),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_local_actor_sessions_valid_expiry",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_local_actor_sessions_valid_revocation",
        ),
        Index(
            "ix_local_actor_sessions_actor_expiry",
            "actor_id",
            "expires_at",
        ),
        Index(
            "ix_local_actor_sessions_actor_revoked",
            "actor_id",
            "revoked_at",
        ),
    )


class LocalRefreshToken(Base):
    """
    One issued opaque refresh token.

    The raw refresh token is never stored.

    Only its SHA-256 fingerprint is persisted.

    Refresh tokens are rotated:
        old token -> consumed
        new token -> created

    If an already consumed token is presented again, the auth service can
    detect token reuse and revoke the entire LocalActorSession.
    """

    __tablename__ = "local_refresh_tokens"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "local_actor_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(REFRESH_TOKEN_HASH_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reuse_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    replaced_by_token_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "local_refresh_tokens.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_local_refresh_tokens_valid_expiry",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="ck_local_refresh_tokens_valid_consumed_at",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_local_refresh_tokens_valid_revoked_at",
        ),
        CheckConstraint(
            "reuse_detected_at IS NULL OR reuse_detected_at >= created_at",
            name="ck_local_refresh_tokens_valid_reuse_at",
        ),
        CheckConstraint(
            "replaced_by_token_id IS NULL OR replaced_by_token_id <> id",
            name="ck_local_refresh_tokens_not_self_replaced",
        ),
        Index(
            "ix_local_refresh_tokens_session_expiry",
            "session_id",
            "expires_at",
        ),
        Index(
            "ix_local_refresh_tokens_session_consumed",
            "session_id",
            "consumed_at",
        ),
    )