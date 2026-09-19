"""Runtime configuration assembly for WEAVE CBT deployments."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote

from ..build_metadata import BuildEnvironment, BuildMetadata


_POSTGRES_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
_MIN_DATABASE_PASSWORD_LENGTH = 12
_DEFAULT_REDIS_URL = "redis://redis:6379/0"
_DATABASE_HOST = "postgres"
_DATABASE_PORT = 5432


@dataclass(frozen=True)
class InstallationConfigInput:
    """Values supplied during installation for the local PostgreSQL instance."""

    database_name: str
    database_user: str
    database_password: str


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated configuration required by the local WEAVE CBT stack."""

    environment: BuildEnvironment
    weave_api_base_url: str
    database_name: str
    database_user: str
    database_password: str
    database_url: str
    redis_url: str

    def as_environment(self) -> dict[str, str]:
        """Return the environment variables required by the CBT runtime."""

        return {
            "ENVIRONMENT": self.environment.value,
            "WEAVE_API_BASE_URL": self.weave_api_base_url,
            "POSTGRES_DB": self.database_name,
            "POSTGRES_USER": self.database_user,
            "POSTGRES_PASSWORD": self.database_password,
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
            "DEBUG": "false",
        }


class ConfigService:
    """Combine immutable build metadata with installation-specific settings."""

    def __init__(self, build_metadata: BuildMetadata) -> None:
        self._build_metadata = build_metadata

    def create_runtime_config(
        self,
        installation: InstallationConfigInput,
    ) -> RuntimeConfig:
        """Validate installer input and construct the final runtime config."""

        database_name = _validate_postgres_identifier(
            installation.database_name,
            field_name="database name",
        )
        database_user = _validate_postgres_identifier(
            installation.database_user,
            field_name="database user",
        )
        database_password = _validate_database_password(
            installation.database_password,
        )

        database_url = _build_database_url(
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
        )

        return RuntimeConfig(
            environment=self._build_metadata.environment,
            weave_api_base_url=self._build_metadata.weave_api_base_url,
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
            database_url=database_url,
            redis_url=_DEFAULT_REDIS_URL,
        )


def _validate_postgres_identifier(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name.capitalize()} must be a string.")

    normalized = value.strip()

    if not _POSTGRES_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"Invalid {field_name}. Use 1-63 characters, start with a letter, "
            "and use only letters, numbers, and underscores."
        )

    return normalized


def _validate_database_password(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Database password must be a string.")

    if len(value) < _MIN_DATABASE_PASSWORD_LENGTH:
        raise ValueError(
            f"Database password must contain at least "
            f"{_MIN_DATABASE_PASSWORD_LENGTH} characters."
        )

    if any(character in value for character in ("\r", "\n", "\x00")):
        raise ValueError(
            "Database password cannot contain line breaks or null characters."
        )

    return value


def _build_database_url(
    *,
    database_name: str,
    database_user: str,
    database_password: str,
) -> str:
    encoded_user = quote(database_user, safe="")
    encoded_password = quote(database_password, safe="")
    encoded_database = quote(database_name, safe="")

    return (
        f"postgresql+asyncpg://{encoded_user}:{encoded_password}"
        f"@{_DATABASE_HOST}:{_DATABASE_PORT}/{encoded_database}"
    )
