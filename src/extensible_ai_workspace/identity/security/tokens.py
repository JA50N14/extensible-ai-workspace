"""Opaque session and CSRF token primitives."""

from dataclasses import dataclass, field
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe

TOKEN_ENTROPY_BYTES = 32


@dataclass(frozen=True, slots=True)
class SessionToken:
    """Raw opaque session credential issued to a client."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        """Reject an empty session token."""

        _require_token_text(
            self.value,
            field_name="session token",
        )

    def hash(self) -> bytes:
        """Return the verifier persisted for this session token."""

        return _hash_token(self.value)


@dataclass(frozen=True, slots=True)
class CsrfToken:
    """Raw CSRF credential issued for one application session."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        """Reject an empty CSRF token."""

        _require_token_text(
            self.value,
            field_name="CSRF token",
        )

    def verifier(self) -> bytes:
        """Return the verifier persisted for this CSRF token."""

        return _hash_token(self.value)


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    """Raw credentials created when establishing a session."""

    session_token: SessionToken
    csrf_token: CsrfToken


def generate_session_credentials() -> SessionCredentials:
    """Generate independent opaque session and CSRF credentials."""

    return SessionCredentials(
        session_token=SessionToken(
            token_urlsafe(TOKEN_ENTROPY_BYTES)
        ),
        csrf_token=CsrfToken(
            token_urlsafe(TOKEN_ENTROPY_BYTES)
        ),
    )


def verify_session_token(
    candidate: SessionToken,
    expected_hash: bytes,
) -> bool:
    """Verify a raw session token against its stored hash."""

    return compare_digest(
        candidate.hash(),
        expected_hash,
    )


def verify_csrf_token(
    candidate: CsrfToken,
    expected_verifier: bytes,
) -> bool:
    """Verify a raw CSRF token against its stored verifier."""

    return compare_digest(
        candidate.verifier(),
        expected_verifier,
    )


def _hash_token(value: str) -> bytes:
    """Hash one opaque token using SHA-256."""

    return sha256(value.encode("utf-8")).digest()


def _require_token_text(
    value: str,
    *,
    field_name: str,
) -> None:
    """Require a nonblank opaque token."""

    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank.")
