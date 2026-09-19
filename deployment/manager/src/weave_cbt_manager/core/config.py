"""Runtime configuration generation for managed WEAVE CBT deployments."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from weave_cbt_manager.constants import (
    DEFAULT_POSTGRES_DB,
    DEFAULT_POSTGRES_USER,
    DEFAULT_WEAVE_API_BASE_URL,
    DEFAULT_WEAVE_IMAGE,
)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    weave_image: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    weave_api_base_url: str

    @classmethod
    def create_default(cls) -> "RuntimeConfig":
        return cls(
            weave_image=DEFAULT_WEAVE_IMAGE,
            postgres_user=DEFAULT_POSTGRES_USER,
            postgres_password=secrets.token_urlsafe(36),
            postgres_db=DEFAULT_POSTGRES_DB,
            weave_api_base_url=DEFAULT_WEAVE_API_BASE_URL,
        )

    def to_env_text(self) -> str:
        return (
            f"WEAVE_IMAGE={self.weave_image}\n"
            f"POSTGRES_USER={self.postgres_user}\n"
            f"POSTGRES_PASSWORD={self.postgres_password}\n"
            f"POSTGRES_DB={self.postgres_db}\n"
            f"WEAVE_API_BASE_URL={self.weave_api_base_url}\n"
        )


class RuntimeConfigService:
    """Creates runtime secrets once and preserves them across app restarts."""

    def __init__(self, env_path: Path) -> None:
        self.env_path = env_path

    def ensure(self, *, image: str | None = None) -> RuntimeConfig:
        if self.env_path.is_file():
            return self.load()

        config = RuntimeConfig.create_default()
        if image:
            config = RuntimeConfig(
                weave_image=image,
                postgres_user=config.postgres_user,
                postgres_password=config.postgres_password,
                postgres_db=config.postgres_db,
                weave_api_base_url=config.weave_api_base_url,
            )

        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text(config.to_env_text(), encoding="utf-8")
        return config

    def load(self) -> RuntimeConfig:
        values: dict[str, str] = {}
        for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

        required = {
            "WEAVE_IMAGE",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "WEAVE_API_BASE_URL",
        }
        missing = sorted(required.difference(values))
        if missing:
            raise RuntimeError(
                f"WEAVE CBT runtime configuration is missing: {', '.join(missing)}"
            )

        return RuntimeConfig(
            weave_image=values["WEAVE_IMAGE"],
            postgres_user=values["POSTGRES_USER"],
            postgres_password=values["POSTGRES_PASSWORD"],
            postgres_db=values["POSTGRES_DB"],
            weave_api_base_url=values["WEAVE_API_BASE_URL"],
        )
