# ========================== #
# backend.app.core.security
# ========================== #

"""
Low-level security primitives for the Weave CBT runtime.

Responsibilities:

- persistent local JWT signing-secret management;
- local actor access-token creation and validation;
- opaque local refresh-token generation and hashing;
- candidate examination PIN generation, hashing, and verification.

Local actors are Weave-authenticated teachers and tenant administrators.
Candidate/student authentication is handled separately by the CBT runtime.

This module does NOT:

- authenticate teachers/admins against Weave;
- pair CBT installations;
- store the Weave installation credential;
- query PostgreSQL;
- create, rotate, or revoke database session records;
- authorize teachers for classes or subjects;
- determine candidate eligibility.

Those responsibilities belong to their respective integration/domain layers.
"""

import asyncio
import hashlib
import os
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.settings import settings

# ========================== #
# LOCAL TOKEN CONSTANTS
# ========================== #

LOCAL_TOKEN_ISSUER = "weave-cbt"
LOCAL_TOKEN_AUDIENCE = "weave-cbt-local"
LOCAL_ACCESS_TOKEN_TYPE = "actor_access"

LOCAL_SIGNING_SECRET_FILENAME = "local_auth.secret"
LOCAL_SIGNING_SECRET_BYTES = 64
MIN_LOCAL_SIGNING_SECRET_LENGTH = 64

REFRESH_TOKEN_BYTES = 64
TOKEN_ID_BYTES = 24


# ========================== #
# CANDIDATE PIN CONSTANTS
# ========================== #

DEFAULT_CANDIDATE_PIN_LENGTH = 6
MIN_CANDIDATE_PIN_LENGTH = 6
MAX_CANDIDATE_PIN_LENGTH = 10


# ========================== #
# RESERVED JWT CLAIMS
# ========================== #

_RESERVED_ACCESS_TOKEN_CLAIMS = frozenset(
    {
        "iss",
        "aud",
        "sub",
        "iat",
        "nbf",
        "exp",
        "jti",
        "sid",
        "role",
        "installation_id",
        "token_type",
    }
)


_password_hash = PasswordHash.recommended()


# ========================== #
# EXCEPTIONS
# ========================== #


class SecurityError(Exception):
    """Base exception for local CBT security failures."""


class SecurityConfigurationError(SecurityError):
    """Raised when persistent local security state is missing or invalid."""


class InvalidLocalTokenError(SecurityError):
    """Raised when a local access token cannot be trusted."""


class ExpiredLocalTokenError(InvalidLocalTokenError):
    """Raised when a local access token has expired."""


class StoredCredentialHashError(SecurityError):
    """Raised when a stored candidate credential hash is invalid."""


# ========================== #
# INTERNAL HELPERS
# ========================== #


def _local_signing_secret_path() -> Path:
    """Return the persistent path of the local JWT signing secret."""

    return settings.IDENTITY_STORAGE_PATH / LOCAL_SIGNING_SECRET_FILENAME


def _ensure_identity_directory(
    path: Path,
) -> None:
    """
    Ensure the persistent identity directory exists and restrict it
    to the CBT container user.
    """

    try:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        os.chmod(
            path,
            0o700,
        )

    except OSError as exc:
        raise SecurityConfigurationError(
            "Unable to initialize the CBT identity directory."
        ) from exc


def _restrict_secret_file_permissions(
    path: Path,
) -> None:
    """
    Restrict the signing-secret file to the CBT container user.

    The CBT application runs inside Linux containers regardless of
    whether Docker is hosted by Windows, macOS, or Linux.
    """

    try:
        os.chmod(
            path,
            0o600,
        )

    except OSError as exc:
        raise SecurityConfigurationError(
            "Unable to restrict local JWT signing-secret permissions."
        ) from exc


def _read_local_signing_secret(
    path: Path,
) -> str:
    """Read and validate the persistent local JWT signing secret."""

    secret = path.read_text(encoding="utf-8").strip()

    if not secret:
        raise SecurityConfigurationError("Local JWT signing-secret file is empty.")

    if len(secret) < MIN_LOCAL_SIGNING_SECRET_LENGTH:
        raise SecurityConfigurationError("Local JWT signing-secret file is invalid.")

    return secret


def _normalize_utc_datetime(
    value: datetime | None,
) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if value is None:
        return datetime.now(UTC)

    if value.tzinfo is None:
        raise ValueError("now must be timezone-aware.")

    return value.astimezone(UTC)


def _require_non_empty_string(
    value: str,
    field_name: str,
) -> str:
    """Normalize and validate a required string."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")  # noqa : TRY004

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    return normalized


def _require_token_claim(
    payload: Mapping[str, Any],
    claim_name: str,
) -> str:
    """Return a required non-empty string JWT claim."""

    value = payload.get(claim_name)

    if not isinstance(value, str) or not value.strip():
        raise InvalidLocalTokenError(
            f"Local access token claim '{claim_name}' is invalid."
        )

    return value


def _is_valid_candidate_pin(
    pin: str,
) -> bool:
    """Return whether a candidate PIN has the required format."""

    if not isinstance(pin, str):
        return False

    if not pin.isdigit():
        return False

    return MIN_CANDIDATE_PIN_LENGTH <= len(pin) <= MAX_CANDIDATE_PIN_LENGTH


def _validate_candidate_pin(
    pin: str,
) -> None:
    """Raise when a candidate PIN has an invalid format."""

    if not _is_valid_candidate_pin(pin):
        raise ValueError(
            "Candidate PIN must contain only digits "
            "and be between "
            f"{MIN_CANDIDATE_PIN_LENGTH} and "
            f"{MAX_CANDIDATE_PIN_LENGTH} "
            "characters long."
        )


# ========================== #
# PERSISTENT SIGNING SECRET
# ========================== #


@lru_cache(maxsize=1)
def get_local_signing_secret() -> str:
    """
    Load the persistent local JWT signing secret.

    This function never creates a new secret.

    Installation/pairing initialization is responsible
    for creating it first.
    """

    secret_path = _local_signing_secret_path()

    try:
        return _read_local_signing_secret(secret_path)

    except FileNotFoundError as exc:
        raise SecurityConfigurationError(
            "Local JWT signing secret has not been initialized."
        ) from exc

    except OSError as exc:
        raise SecurityConfigurationError(
            "Unable to read the local JWT signing secret."
        ) from exc


def ensure_local_signing_secret() -> str:
    """
    Return the persistent local JWT signing secret,
    creating it if necessary.

    This should normally be called by the successful installation
    pairing flow, not automatically during generic application startup.

    IDENTITY_STORAGE_PATH must use persistent Docker storage so the
    secret survives:

    - API container replacement;
    - image upgrades;
    - Docker restarts;
    - host restarts.
    """

    secret_path = _local_signing_secret_path()

    _ensure_identity_directory(secret_path.parent)

    try:
        existing_secret = _read_local_signing_secret(secret_path)

    except FileNotFoundError:
        existing_secret = None

    except OSError as exc:
        raise SecurityConfigurationError(
            "Unable to read the local JWT signing secret."
        ) from exc

    if existing_secret is not None:
        _restrict_secret_file_permissions(secret_path)

        return existing_secret

    secret = secrets.token_urlsafe(LOCAL_SIGNING_SECRET_BYTES)

    try:
        file_descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

    except FileExistsError:
        try:
            return _read_local_signing_secret(secret_path)

        except OSError as exc:
            raise SecurityConfigurationError(
                "Unable to read the local JWT signing secret."
            ) from exc

    except OSError as exc:
        raise SecurityConfigurationError(
            "Unable to create the local JWT signing secret."
        ) from exc

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
        ) as secret_file:
            secret_file.write(secret)

            secret_file.flush()

            os.fsync(secret_file.fileno())

    except Exception:
        try:
            secret_path.unlink()

        except FileNotFoundError:
            pass

        raise

    _restrict_secret_file_permissions(secret_path)

    get_local_signing_secret.cache_clear()

    return secret


# ========================== #
# GENERAL TOKEN PRIMITIVES
# ========================== #


def generate_token_id() -> str:
    """
    Generate a unique and unpredictable identifier for a token.
    """

    return secrets.token_urlsafe(TOKEN_ID_BYTES)


def generate_refresh_token() -> str:
    """
    Generate a high-entropy opaque local refresh token.

    The refresh token carries no identity claims.

    The raw value is returned to the client while only its
    SHA-256 fingerprint should be persisted in PostgreSQL.
    """

    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(
    token: str,
) -> str:
    """
    Return the SHA-256 fingerprint of a refresh token.

    Refresh tokens are high-entropy random secrets, so they do not
    require slow password hashing such as Argon2.
    """

    if not isinstance(token, str) or not token:
        raise ValueError("Refresh token cannot be empty.")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_refresh_token(
    token: str,
    expected_hash: str,
) -> bool:
    """
    Compare a raw refresh token against its stored fingerprint.

    Expiration, rotation, revocation, reuse detection,
    and session ownership belong to the auth domain.
    """

    if (
        not isinstance(token, str)
        or not token
        or not isinstance(expected_hash, str)
        or not expected_hash
    ):
        return False

    candidate_hash = hash_refresh_token(token)

    return secrets.compare_digest(
        candidate_hash,
        expected_hash,
    )


# ========================== #
# LOCAL ACTOR ACCESS TOKENS
# ========================== #


def create_local_access_token(
    *,
    subject: str,
    session_id: str,
    role: str,
    installation_id: str,
    additional_claims: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> str:
    """
    Create a short-lived local access JWT for a
    Weave-authenticated actor.

    Local actors currently include:

    - teachers;
    - tenant administrators.

    Parameters
    ----------
    subject:
        The authenticated Weave actor identifier.

    session_id:
        The local CBT session identifier stored in PostgreSQL.

    role:
        The actor's role returned by Weave authentication.

    installation_id:
        The paired CBT installation identifier.

    additional_claims:
        Optional non-security-critical contextual claims,
        such as a Weave membership identifier.

    now:
        Optional timezone-aware datetime used primarily for testing.

    Class-subject assignments are intentionally not embedded into
    the JWT.

    They should be checked against local academic projections so
    assignment changes can take effect without waiting for an
    access token to expire.
    """

    subject = _require_non_empty_string(
        subject,
        "subject",
    )

    session_id = _require_non_empty_string(
        session_id,
        "session_id",
    )

    role = _require_non_empty_string(
        role,
        "role",
    )

    installation_id = _require_non_empty_string(
        installation_id,
        "installation_id",
    )

    issued_at = _normalize_utc_datetime(now)

    expires_at = issued_at + timedelta(
        minutes=(settings.LOCAL_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "iss": LOCAL_TOKEN_ISSUER,
        "aud": LOCAL_TOKEN_AUDIENCE,
        "sub": subject,
        "iat": int(issued_at.timestamp()),
        "nbf": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": generate_token_id(),
        "sid": session_id,
        "role": role,
        "installation_id": installation_id,
        "token_type": LOCAL_ACCESS_TOKEN_TYPE,
    }

    if additional_claims:
        protected_claims = _RESERVED_ACCESS_TOKEN_CLAIMS & set(additional_claims)

        if protected_claims:
            claim_names = ", ".join(sorted(protected_claims))

            raise ValueError(
                f"additional_claims cannot override protected JWT claims: {claim_names}"
            )

        payload.update(additional_claims)

    return jwt.encode(
        payload,
        get_local_signing_secret(),
        algorithm=settings.LOCAL_JWT_ALGORITHM,
    )


def decode_local_access_token(
    token: str,
) -> dict[str, Any]:
    """
    Validate and decode a local actor access JWT.

    Validation includes:

    - signature;
    - expiration;
    - not-before time;
    - issued-at time;
    - issuer;
    - audience;
    - subject;
    - JWT identifier;
    - local session identifier;
    - actor role;
    - installation identifier;
    - token type.
    """

    if not isinstance(token, str) or not token.strip():
        raise InvalidLocalTokenError("Local access token is missing.")

    try:
        payload = jwt.decode(
            token,
            key=get_local_signing_secret(),
            algorithms=[
                settings.LOCAL_JWT_ALGORITHM,
            ],
            audience=LOCAL_TOKEN_AUDIENCE,
            issuer=LOCAL_TOKEN_ISSUER,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": True,
                "verify_sub": True,
                "verify_jti": True,
                "require_exp": True,
                "require_iat": True,
                "require_nbf": True,
                "require_iss": True,
                "require_aud": True,
                "require_sub": True,
                "require_jti": True,
            },
        )

    except ExpiredSignatureError as exc:
        raise ExpiredLocalTokenError("Local access token has expired.") from exc

    except JWTError as exc:
        raise InvalidLocalTokenError("Local access token is invalid.") from exc

    _require_token_claim(
        payload,
        "sub",
    )

    _require_token_claim(
        payload,
        "jti",
    )

    _require_token_claim(
        payload,
        "sid",
    )

    _require_token_claim(
        payload,
        "role",
    )

    _require_token_claim(
        payload,
        "installation_id",
    )

    token_type = _require_token_claim(
        payload,
        "token_type",
    )

    if token_type != LOCAL_ACCESS_TOKEN_TYPE:
        raise InvalidLocalTokenError("Unexpected local token type.")

    return payload


# ========================== #
# CANDIDATE EXAM PIN
# ========================== #


def generate_candidate_pin(
    length: int = DEFAULT_CANDIDATE_PIN_LENGTH,
) -> str:
    """
    Generate a cryptographically secure numeric examination PIN.

    PIN uniqueness for a particular examination is a domain/database
    responsibility and is intentionally not handled here.
    """

    if not (MIN_CANDIDATE_PIN_LENGTH <= length <= MAX_CANDIDATE_PIN_LENGTH):
        raise ValueError(
            "Candidate PIN length must be between "
            f"{MIN_CANDIDATE_PIN_LENGTH} and "
            f"{MAX_CANDIDATE_PIN_LENGTH} digits."
        )

    upper_bound = 10**length

    value = secrets.randbelow(upper_bound)

    return f"{value:0{length}d}"


async def hash_candidate_pin(
    pin: str,
) -> str:
    """
    Hash a candidate examination PIN.

    Password hashing is CPU-intensive, so it is moved to a worker
    thread rather than blocking FastAPI's async event loop.
    """

    _validate_candidate_pin(pin)

    return await asyncio.to_thread(
        _password_hash.hash,
        pin,
    )


async def verify_candidate_pin(
    pin: str,
    hashed_pin: str,
) -> bool:
    """
    Verify a candidate examination PIN against its stored hash.
    """

    if not _is_valid_candidate_pin(pin):
        return False

    if not isinstance(hashed_pin, str) or not hashed_pin:
        return False

    try:
        return await asyncio.to_thread(
            _password_hash.verify,
            pin,
            hashed_pin,
        )

    except UnknownHashError as exc:
        raise StoredCredentialHashError(
            "Stored candidate PIN hash is invalid."
        ) from exc
