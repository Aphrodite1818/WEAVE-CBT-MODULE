# ========================== #
# backend.app.core.settings
# ========================== #

"""
Runtime configuration for the Weave CBT application.

Architecture rules:

- PostgreSQL is the durable source of truth for local examination state.
- Redis is used only for caching, coordination, rate limiting, and workers.
- Weave remains authoritative for staff identity and academic data.
- The local CBT runtime owns its own staff sessions after Weave authentication.
- Active examinations must not depend on continuous Weave connectivity.
- Installation identity and credentials are persistent runtime state and are
  not configured through environment variables.
"""

from enum import Enum as PyEnum
from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, PyEnum):
    """Supported application runtime environments."""

    DEVELOPMENT = "dev"
    STAGING = "stg"
    PRODUCTION = "prod"


class Settings(BaseSettings):
    """Application runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
        frozen=True,
    )

    # ========================== #
    # APPLICATION
    # ========================== #

    APP_NAME: str = "Weave CBT"
    APP_VERSION: str = "0.1.0"

    ENVIRONMENT: Environment = Environment.PRODUCTION

    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"

    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)

    LOG_LEVEL: str = "INFO"

    # ========================== #
    # POSTGRESQL
    # ========================== #

    DATABASE_URL: str = Field(
        ...,
        min_length=1,
        description=("Required PostgreSQL connection URL for the local CBT database."),
    )

    # These values are intentionally conservative because multiple
    # FastAPI worker processes each maintain their own SQLAlchemy pool.
    #
    # Example:
    # 4 API workers × (5 pool + 5 overflow)
    # = maximum burst capacity of 40 connections.
    #
    # Tune these values through load testing rather than increasing
    # them arbitrarily.
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=5, ge=0)

    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(
        default=10,
        ge=1,
    )

    DATABASE_POOL_RECYCLE_SECONDS: int = Field(
        default=1800,
        ge=60,
    )

    # ========================== #
    # REDIS
    # ========================== #

    REDIS_URL: str = Field(
        ...,
        min_length=1,
        description=(
            "Redis connection URL used for cache, coordination, "
            "rate limiting, and other temporary state."
        ),
    )

    REDIS_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=5.0,
        gt=0,
    )

    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(
        default=5.0,
        gt=0,
    )

    REDIS_HEALTH_CHECK_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=1,
    )

    REDIS_MAX_CONNECTIONS: int = Field(default=20, ge=1)
    # Taskiq may use a separate Redis database/instance when desired.
    #
    # If omitted, the normal REDIS_URL is reused.
    TASKIQ_REDIS_URL: str | None = None

    # ========================== #
    # PERSISTENT CBT IDENTITY
    # ========================== #

    # This directory must be backed by persistent Docker storage in
    # production.
    #
    # It survives:
    # - container replacement;
    # - image updates;
    # - Docker restarts;
    # - host restarts.
    #
    # Local development may override this through `.env`, for example:
    # `IDENTITY_STORAGE_PATH=./.weave-cbt/identity`.
    #
    # Runtime installation state such as the Weave-issued installation
    # credential and local JWT signing secret belongs here.
    #
    # Do NOT put the installation credential itself into Settings.
    IDENTITY_STORAGE_PATH: Path = Path("/var/lib/weave-cbt/identity")

    # ==========================#
    # LOCAL MEDIA STORAGE
    # ==========================#
    MEDIA_STORAGE_PATH: Path = Path("/var/lib/weave-cbt/media")
    MEDIA_MAX_IMAGE_SIZE_BYTES: int = Field(default=5 * 1024 * 1024, ge=1)

    # ========================== #
    # LOCAL STAFF AUTHENTICATION
    # ========================== #

    # Weave authenticates the teacher/admin initially.
    #
    # After successful authentication, CBT issues its own local tokens.
    # Refreshing these local tokens must not require resending the
    # user's Weave password.
    LOCAL_JWT_ALGORITHM: str = "HS256"

    LOCAL_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=5,
        ge=1,
    )

    LOCAL_REFRESH_TOKEN_EXPIRE_HOURS: int = Field(
        default=12,
        ge=1,
    )

    # ========================== #
    # WEAVE CLOUD INTEGRATION
    # ========================== #

    # The official Weave endpoint is part of the packaged product.
    #
    # Schools should not manually configure this during installation.
    # Development and staging environments may override it.
    WEAVE_API_BASE_URL: AnyHttpUrl = "https://api.weavecloudspace.com"

    WEAVE_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        gt=0,
    )

    WEAVE_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=5.0,
        gt=0,
    )

    # ========================== #
    # HTTP / FRONTEND
    # ========================== #

    # Production is expected to serve the frontend and API through
    # the same local Nginx origin.
    #
    # localhost is retained for local Vite development.
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
        ]
    )

    # ========================== #
    # SENTRY
    # ========================== #

    SENTRY_BACKEND_DSN_URL: str | None = None

    # ========================== #
    # DERIVED CONFIGURATION
    # ========================== #

    @property
    def taskiq_redis_url(self) -> str:
        """
        Return the Redis URL Taskiq should use.

        A dedicated Taskiq URL may be configured when desired.
        Otherwise the application's normal Redis connection is reused.
        """

        return self.TASKIQ_REDIS_URL or self.REDIS_URL

    # ========================== #
    # VALIDATION
    # ========================== #

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """
        Normalize common PostgreSQL URLs to SQLAlchemy's
        asyncpg-compatible connection scheme.
        """

        value = value.strip()

        prefix_mappings = {
            "postgresql://": "postgresql+asyncpg://",
            "postgres://": "postgresql+asyncpg://",
            "postgresql+psycopg://": "postgresql+asyncpg://",
            "postgresql+psycopg2://": "postgresql+asyncpg://",
        }

        for source_prefix, async_prefix in prefix_mappings.items():
            if value.startswith(source_prefix):
                return value.replace(
                    source_prefix,
                    async_prefix,
                    1,
                )

        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use PostgreSQL with the asyncpg driver."
            )

        return value

    @field_validator("REDIS_URL", "TASKIQ_REDIS_URL")
    @classmethod
    def validate_redis_url(
        cls,
        value: str | None,
    ) -> str | None:
        """Validate Redis connection URLs."""

        if value is None:
            return None

        value = value.strip()

        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URLs must use either 'redis://' or 'rediss://'.")

        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize and validate the configured log level."""

        normalized = value.strip().upper()

        valid_levels = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if normalized not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of: {', '.join(sorted(valid_levels))}"
            )

        return normalized

    @field_validator("LOCAL_JWT_ALGORITHM")
    @classmethod
    def validate_local_jwt_algorithm(
        cls,
        value: str,
    ) -> str:
        """
        Restrict the local authentication implementation to the
        algorithm supported by the CBT security module.
        """

        normalized = value.strip().upper()

        if normalized != "HS256":
            raise ValueError("LOCAL_JWT_ALGORITHM must currently be HS256.")

        return normalized

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(
        cls,
        value: list[str],
    ) -> list[str]:
        """Normalize configured frontend origins."""

        normalized: list[str] = []

        for origin in value:
            origin = origin.strip().rstrip("/")

            if not origin:
                continue

            if origin == "*":
                normalized.append(origin)
                continue

            if not origin.startswith(("http://", "https://")):
                raise ValueError(
                    "CORS_ORIGINS entries must use 'http://' or 'https://'."
                )

            normalized.append(origin)

        return normalized

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """Validate configuration involving multiple settings."""

        if self.ENVIRONMENT == Environment.PRODUCTION and self.DEBUG:
            raise ValueError("DEBUG must be disabled in production.")

        if self.ENVIRONMENT == Environment.PRODUCTION and "*" in self.CORS_ORIGINS:
            raise ValueError("Wildcard CORS origins are not allowed in production.")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the process-wide application settings instance.

    Settings are loaded once, validated, cached, and frozen for
    the lifetime of the process.
    """

    return Settings()


settings = get_settings()
