"""Durable local copy of effective Weave tenant branding."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BrandingState(Base):
    """Last effective light-mode branding received from Weave for this tenant."""

    __tablename__ = "branding_states"

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, unique=True, index=True)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_revision: Mapped[UUID | None] = mapped_column(nullable=True)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_default_theme: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    theme_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    token_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    light_tokens: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("theme_version >= 0", name="ck_branding_states_theme_version_nonnegative"),
        CheckConstraint(
            "token_schema_version >= 1",
            name="ck_branding_states_token_schema_version_positive",
        ),
    )
