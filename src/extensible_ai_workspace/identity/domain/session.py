"""Application-session domain model."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AuthenticationMethod(StrEnum):
    """Supported session authentication methods."""

    LOCAL_TRUSTED = "LOCAL_TRUSTED"
    OIDC = "OIDC"


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationSession:
    """Server-side representation of an authenticated session."""

    id: UUID
    user_id: UUID
    external_identity_id: UUID | None
    authentication_method: AuthenticationMethod
    session_token_hash: bytes
    csrf_verifier: bytes
    created_at: datetime
    last_activity_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    authenticated_at: datetime
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    rotation_generation: int = 1
    security_context_version: int = 1

    def __post_init__(self) -> None:
        """Reject invalid session state."""

        timestamp_fields = {
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "idle_expires_at": self.idle_expires_at,
            "absolute_expires_at": self.absolute_expires_at,
            "authenticated_at": self.authenticated_at,
        }

        for field_name, value in timestamp_fields.items():
            _require_aware_datetime(
                value,
                field_name=field_name,
            )

        if self.revoked_at is not None:
            _require_aware_datetime(
                self.revoked_at,
                field_name="revoked_at",
            )

        if not self.session_token_hash:
            raise ValueError(
                "session_token_hash cannot be empty."
            )

        if not self.csrf_verifier:
            raise ValueError(
                "csrf_verifier cannot be empty."
            )

        if self.last_activity_at < self.created_at:
            raise ValueError(
                "last_activity_at cannot precede created_at."
            )

        if self.idle_expires_at <= self.created_at:
            raise ValueError(
                "idle_expires_at must be later than created_at."
            )

        if self.absolute_expires_at <= self.created_at:
            raise ValueError(
                "absolute_expires_at must be later than created_at."
            )

        if self.idle_expires_at > self.absolute_expires_at:
            raise ValueError(
                "idle_expires_at cannot be later than "
                "absolute_expires_at."
            )

        if self.authenticated_at > self.created_at:
            raise ValueError(
                "authenticated_at cannot be later than created_at."
            )

        if self.revoked_at is None and self.revocation_reason is not None:
            raise ValueError(
                "An active session cannot have a revocation reason."
            )

        if self.revoked_at is not None:
            if self.revoked_at < self.created_at:
                raise ValueError(
                    "revoked_at cannot precede created_at."
                )

            if (
                self.revocation_reason is None
                or not self.revocation_reason.strip()
            ):
                raise ValueError(
                    "A revoked session requires a revocation reason."
                )

        if self.rotation_generation < 1:
            raise ValueError(
                "rotation_generation must be at least 1."
            )

        if self.security_context_version < 1:
            raise ValueError(
                "security_context_version must be at least 1."
            )

    @property
    def is_revoked(self) -> bool:
        """Return whether the session has been revoked."""

        return self.revoked_at is not None

    def is_valid_at(self, current_time: datetime) -> bool:
        """Return whether the session is valid at a given time."""

        _require_aware_datetime(
            current_time,
            field_name="current_time",
        )

        return (
            not self.is_revoked
            and current_time < self.idle_expires_at
            and current_time < self.absolute_expires_at
        )

    def revoke(
        self,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> "ApplicationSession":
        """Return a revoked replacement for this session."""

        if self.is_revoked:
            raise ValueError(
                "A revoked session cannot be revoked again."
            )

        if not reason.strip():
            raise ValueError(
                "A revocation reason cannot be blank."
            )

        return replace(
            self,
            revoked_at=revoked_at,
            revocation_reason=reason.strip(),
        )


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> None:
    """Require a timezone-aware timestamp."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware."
        )
