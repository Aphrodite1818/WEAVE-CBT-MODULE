"""Runtime configuration assembly for WEAVE CBT deployments."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote

from ..build_metadata import BuildMetadata

_POSTGRES_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
_MIN_DATABASE_PASSWORD_LENGTH = 12
_DATABASE_HOST = "postgres"
_DATABASE_PORT = 5432
_REDIS_URL = "redis://redis:6379/0"


@dataclass(frozen=True, slots=True)
class InstallationConfigInput:
    database_name: str
    database_user: str
    database_password: str


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    environment: str
    weave_api_base_url: str
    weave_image: str
    database_name: str
    database_user: str
    database_password: str
    database_url: str
    redis_url: str

    def as_environment(self) -> dict[str, str]:
        return {
            "ENVIRONMENT": self.environment,
            "WEAVE_API_BASE_URL": self.weave_api_base_url,
            "WEAVE_IMAGE": self.weave_image,
            "POSTGRES_DB": self.database_name,
            "POSTGRES_USER": self.database_user,
            "POSTGRES_PASSWORD": self.database_password,
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
            "DEBUG": "false",
        }


class ConfigService:
    def __init__(self, build_metadata: BuildMetadata) -> None:
        self._build_metadata = build_metadata

    def create_runtime_config(self, installation: InstallationConfigInput) -> RuntimeConfig:
        database_name = _validate_postgres_identifier(installation.database_name, field_name="database name")
        database_user = _validate_postgres_identifier(installation.database_user, field_name="database user")
        database_password = _validate_database_password(installation.database_password)
        database_url = _build_database_url(
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
        )
        return RuntimeConfig(
            environment=self._build_metadata.environment.value,
            weave_api_base_url=self._build_metadata.weave_api_base_url,
            weave_image=self._build_metadata.weave_image,
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
            database_url=database_url,
            redis_url=_REDIS_URL,
        )


def _validate_postgres_identifier(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name.capitalize()} must be a string.")
    normalized = value.strip()
    if not _POSTGRES_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"Invalid {field_name}. Use 1-63 characters, begin with a letter, "
            "and use only letters, numbers, and underscores."
        )
    return normalized


def _validate_database_password(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Database password must be a string.")
    if len(value) < _MIN_DATABASE_PASSWORD_LENGTH:
        raise ValueError(f"Database password must contain at least {_MIN_DATABASE_PASSWORD_LENGTH} characters.")
    if any(character in value for character in ("\r", "\n", "\x00")):
        raise ValueError("Database password cannot contain line breaks or null characters.")
    return value


def _build_database_url(*, database_name: str, database_user: str, database_password: str) -> str:
    return (
        "postgresql+asyncpg://"
        f"{quote(database_user, safe='')}:{quote(database_password, safe='')}"
        f"@{_DATABASE_HOST}:{_DATABASE_PORT}/{quote(database_name, safe='')}"
    )


def render_runtime_env(config: RuntimeConfig) -> str:
    return "\n".join(
        f"{key}={_quote_env_value(value)}"
        for key, value in config.as_environment().items()
    ) + "\n"


def _quote_env_value(value: str) -> str:
    if any(character in value for character in ("\r", "\n", "\x00")):
        raise ValueError("Environment variable values cannot contain line breaks or null characters.")
    return "'" + value.replace("'", "\\'") + "'"
