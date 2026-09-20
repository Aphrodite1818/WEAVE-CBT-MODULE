"""Build-time identity for the WEAVE CBT Manager."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from urllib.parse import urlparse

try:
    from .generated_build import CBT_VERSION, ENVIRONMENT, WEAVE_API_BASE_URL, WEAVE_IMAGE
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "Build metadata is missing. For local development, copy "
        "generated_build.py.example to generated_build.py. Packaged builds "
        "must generate generated_build.py during CI."
    ) from exc


class BuildEnvironment(str, Enum):
    DEV = "dev"
    STAGING = "stg"
    PROD = "prod"


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    environment: BuildEnvironment
    weave_api_base_url: str
    weave_image: str
    cbt_version: str

    @property
    def channel(self) -> str:
        if self.environment is BuildEnvironment.STAGING:
            return "staging"
        if self.environment is BuildEnvironment.PROD:
            return "production"
        return "development"


def _parse_environment(value: object) -> BuildEnvironment:
    if not isinstance(value, str):
        raise ValueError("ENVIRONMENT must be a string.")
    normalized = value.strip().lower()
    try:
        return BuildEnvironment(normalized)
    except ValueError as exc:
        supported = ", ".join(item.value for item in BuildEnvironment)
        raise ValueError(f"Unsupported build environment {value!r}. Expected: {supported}.") from exc


def _validate_api_url(value: object, environment: BuildEnvironment) -> str:
    if not isinstance(value, str):
        raise ValueError("WEAVE_API_BASE_URL must be a string.")
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid WEAVE API base URL: {value!r}.")
    if environment in {BuildEnvironment.STAGING, BuildEnvironment.PROD} and parsed.scheme != "https":
        raise ValueError(f"{environment.value} builds require an HTTPS WEAVE API URL.")
    return normalized


def _validate_image(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("WEAVE_IMAGE must be a string.")
    normalized = value.strip()
    if not normalized or any(character.isspace() for character in normalized):
        raise ValueError("WEAVE_IMAGE must be a non-empty container image reference.")
    if ":" not in normalized and "@sha256:" not in normalized:
        raise ValueError("WEAVE_IMAGE must be pinned to a tag or digest.")
    return normalized


def _validate_version(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("CBT_VERSION must be a string.")
    normalized = value.strip().lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", normalized):
        raise ValueError(f"Invalid CBT_VERSION: {value!r}.")
    return normalized


def load_build_metadata() -> BuildMetadata:
    environment = _parse_environment(ENVIRONMENT)
    return BuildMetadata(
        environment=environment,
        weave_api_base_url=_validate_api_url(WEAVE_API_BASE_URL, environment),
        weave_image=_validate_image(WEAVE_IMAGE),
        cbt_version=_validate_version(CBT_VERSION),
    )


BUILD_METADATA = load_build_metadata()
