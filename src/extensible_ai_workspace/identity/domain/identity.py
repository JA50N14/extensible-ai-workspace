"""Identity and user domain models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserStatus(StrEnum):
    """Supported internal-user lifecycle states."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETION_REQUESTED = "DELETION_REQUESTED"
    PURGED = "PURGED"


class IdentityProviderType(StrEnum):
    """Supported external identity provider types."""

    LOCAL_TRUSTED = "LOCAL_TRUSTED"
    OIDC = "OIDC"


@dataclass(frozen=True, slots=True, kw_only=True)
class InternalUser:
    """Stable application identity owned by the platform."""

    id: UUID
    status: UserStatus
    display_name: str
    primary_email: str | None
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None = None
    deletion_requested_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        """Reject invalid internal-user state."""

        _require_text(self.display_name, field_name="display_name")
        _require_aware_datetime(
            self.created_at,
            field_name="created_at",
        )
        _require_aware_datetime(
            self.updated_at,
            field_name="updated_at",
        )

        if self.primary_email is not None:
            _require_text(
                self.primary_email,
                field_name="primary_email",
            )

        if self.disabled_at is not None:
            _require_aware_datetime(
                self.disabled_at,
                field_name="disabled_at",
            )

        if self.deletion_requested_at is not None:
            _require_aware_datetime(
                self.deletion_requested_at,
                field_name="deletion_requested_at",
            )

        if self.version < 1:
            raise ValueError("version must be at least 1.")

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot precede created_at."
            )

        if (
            self.status is UserStatus.ACTIVE
            and self.disabled_at is not None
        ):
            raise ValueError(
                "An active user cannot have disabled_at set."
            )

        if (
            self.status is UserStatus.DISABLED
            and self.disabled_at is None
        ):
            raise ValueError(
                "A disabled user must have disabled_at set."
            )

        if (
            self.status is UserStatus.DELETION_REQUESTED
            and self.deletion_requested_at is None
        ):
            raise ValueError(
                "A deletion-requested user must have "
                "deletion_requested_at set."
            )

    @property
    def is_active(self) -> bool:
        """Return whether the user can authenticate normally."""

        return self.status is UserStatus.ACTIVE


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalIdentity:
    """Mapping from an authentication provider to an internal user."""

    id: UUID
    user_id: UUID
    provider_type: IdentityProviderType
    issuer: str
    subject: str
    created_at: datetime
    last_authenticated_at: datetime | None = None
    disabled_at: datetime | None = None
    claims_profile_version: int = 1

    def __post_init__(self) -> None:
        """Reject invalid external-identity state."""

        _require_text(self.issuer, field_name="issuer")
        _require_text(self.subject, field_name="subject")
        _require_aware_datetime(
            self.created_at,
            field_name="created_at",
        )

        if self.last_authenticated_at is not None:
            _require_aware_datetime(
                self.last_authenticated_at,
                field_name="last_authenticated_at",
            )

            if self.last_authenticated_at < self.created_at:
                raise ValueError(
                    "last_authenticated_at cannot precede created_at."
                )

        if self.disabled_at is not None:
            _require_aware_datetime(
                self.disabled_at,
                field_name="disabled_at",
            )

            if self.disabled_at < self.created_at:
                raise ValueError(
                    "disabled_at cannot precede created_at."
                )

        if self.claims_profile_version < 1:
            raise ValueError(
                "claims_profile_version must be at least 1."
            )

    @property
    def is_enabled(self) -> bool:
        """Return whether this identity mapping remains enabled."""

        return self.disabled_at is None


def _require_text(
    value: str,
    *,
    field_name: str,
) -> None:
    """Require nonblank textual domain data."""

    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank.")


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
