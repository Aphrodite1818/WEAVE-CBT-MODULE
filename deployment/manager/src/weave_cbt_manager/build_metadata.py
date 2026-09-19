"""Build-time identity for the WEAVE CBT Manager.

The actual values come from ``generated_build.py``. CI creates that module for
packaged builds, while developers can create it locally from
``generated_build.py.example``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

try:
    from .generated_build import ENVIRONMENT, WEAVE_API_BASE_URL
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "Build metadata is missing. For local development, copy "
        "generated_build.py.example to generated_build.py. "
        "Packaged builds must generate generated_build.py during CI."
    ) from exc


class BuildEnvironment(str, Enum):
    """Supported WEAVE environments for a Manager build."""

    DEV = "dev"
    STAGING = "stg"
    PROD = "prod"


@dataclass(frozen=True)
class BuildMetadata:
    """Validated immutable identity of this Manager build."""

    environment: BuildEnvironment
    weave_api_base_url: str


def _parse_environment(value: object) -> BuildEnvironment:
    if not isinstance(value, str):
        raise ValueError("ENVIRONMENT must be a string.")

    normalized = value.strip().lower()

    try:
        return BuildEnvironment(normalized)
    except ValueError as exc:
        supported = ", ".join(environment.value for environment in BuildEnvironment)
        raise ValueError(
            f"Unsupported build environment {value!r}. Expected one of: {supported}."
        ) from exc


def _validate_api_url(value: object, environment: BuildEnvironment) -> str:
    if not isinstance(value, str):
        raise ValueError("WEAVE_API_BASE_URL must be a string.")

    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid WEAVE API base URL: {value!r}.")

    if environment in {BuildEnvironment.STAGING, BuildEnvironment.PROD}:
        if parsed.scheme != "https":
            raise ValueError(
                f"{environment.value} builds require an HTTPS WEAVE API URL."
            )

    return normalized


def load_build_metadata() -> BuildMetadata:
    """Load and validate the build metadata generated for this binary."""

    environment = _parse_environment(ENVIRONMENT)
    weave_api_base_url = _validate_api_url(WEAVE_API_BASE_URL, environment)

    return BuildMetadata(
        environment=environment,
        weave_api_base_url=weave_api_base_url,
    )


BUILD_METADATA = load_build_metadata()
