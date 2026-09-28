"""Workspace domain model."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

MAX_WORKSPACE_NAME_LENGTH = 200
MAX_WORKSPACE_DESCRIPTION_LENGTH = 2_000


class WorkspaceStatus(StrEnum):
    """Supported workspace lifecycle states."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETION_REQUESTED = "DELETION_REQUESTED"
    PURGED = "PURGED"


@dataclass(frozen=True, slots=True, kw_only=True)
class Workspace:
    """Principal ownership and authorization boundary."""

    id: UUID
    owner_user_id: UUID
    name: str
    description: str | None
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deletion_requested_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        """Normalize metadata and reject invalid workspace state."""

        normalized_name = self.name.strip()

        if not normalized_name:
            raise ValueError("name cannot be blank.")

        if len(normalized_name) > MAX_WORKSPACE_NAME_LENGTH:
            raise ValueError(
                "name cannot exceed "
                f"{MAX_WORKSPACE_NAME_LENGTH} characters."
            )

        normalized_description = _normalize_description(
            self.description
        )

        object.__setattr__(
            self,
            "name",
            normalized_name,
        )
        object.__setattr__(
            self,
            "description",
            normalized_description,
        )

        _require_aware_datetime(
            self.created_at,
            field_name="created_at",
        )
        _require_aware_datetime(
            self.updated_at,
            field_name="updated_at",
        )

        if self.archived_at is not None:
            _require_aware_datetime(
                self.archived_at,
                field_name="archived_at",
            )

            if self.archived_at < self.created_at:
                raise ValueError(
                    "archived_at cannot precede created_at."
                )

        if self.deletion_requested_at is not None:
            _require_aware_datetime(
                self.deletion_requested_at,
                field_name="deletion_requested_at",
            )

            if self.deletion_requested_at < self.created_at:
                raise ValueError(
                    "deletion_requested_at cannot precede "
                    "created_at."
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot precede created_at."
            )

        if self.version < 1:
            raise ValueError("version must be at least 1.")

        self._validate_lifecycle_state()

    @property
    def is_available(self) -> bool:
        """Return whether the workspace is normally available."""

        return self.status is WorkspaceStatus.ACTIVE

    def _validate_lifecycle_state(self) -> None:
        """Require timestamps consistent with the lifecycle status."""

        if self.status is WorkspaceStatus.ACTIVE:
            if self.archived_at is not None:
                raise ValueError(
                    "An active workspace cannot have "
                    "archived_at set."
                )

            if self.deletion_requested_at is not None:
                raise ValueError(
                    "An active workspace cannot have "
                    "deletion_requested_at set."
                )

        if self.status is WorkspaceStatus.ARCHIVED:
            if self.archived_at is None:
                raise ValueError(
                    "An archived workspace must have "
                    "archived_at set."
                )

            if self.deletion_requested_at is not None:
                raise ValueError(
                    "An archived workspace cannot have "
                    "deletion_requested_at set."
                )

        if (
            self.status
            is WorkspaceStatus.DELETION_REQUESTED
            and self.deletion_requested_at is None
        ):
            raise ValueError(
                "A deletion-requested workspace must have "
                "deletion_requested_at set."
            )


def _normalize_description(
    value: str | None,
) -> str | None:
    """Normalize optional workspace description text."""

    if value is None:
        return None

    normalized_value = value.strip()

    if not normalized_value:
        return None

    if len(normalized_value) > MAX_WORKSPACE_DESCRIPTION_LENGTH:
        raise ValueError(
            "description cannot exceed "
            f"{MAX_WORKSPACE_DESCRIPTION_LENGTH} characters."
        )

    return normalized_value


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
