from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from extensible_ai_workspace.workspace.domain import (
    MAX_WORKSPACE_DESCRIPTION_LENGTH,
    MAX_WORKSPACE_NAME_LENGTH,
    Workspace,
    WorkspaceStatus,
)

WORKSPACE_ID = UUID(
    "01990000-0000-7000-8000-000000000401"
)
OWNER_USER_ID = UUID(
    "01990000-0000-7000-8000-000000000402"
)
CREATED_AT = datetime(
    2026,
    9,
    23,
    12,
    0,
    tzinfo=UTC,
)


def create_workspace(
    **overrides: object,
) -> Workspace:
    values: dict[str, object] = {
        "id": WORKSPACE_ID,
        "owner_user_id": OWNER_USER_ID,
        "name": "Research Workspace",
        "description": "Initial research workspace.",
        "status": WorkspaceStatus.ACTIVE,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    values.update(overrides)

    return Workspace(**values)  # type: ignore[arg-type]


def test_active_workspace_is_available() -> None:
    workspace = create_workspace()

    assert workspace.is_available is True
    assert workspace.version == 1


def test_workspace_normalizes_name_and_description() -> None:
    workspace = create_workspace(
        name="  Research Workspace  ",
        description="  Initial research workspace.  ",
    )

    assert workspace.name == "Research Workspace"
    assert workspace.description == (
        "Initial research workspace."
    )


@pytest.mark.parametrize(
    "description",
    [
        None,
        "",
        "   ",
    ],
)
def test_workspace_normalizes_empty_description_to_none(
    description: str | None,
) -> None:
    workspace = create_workspace(
        description=description,
    )

    assert workspace.description is None


def test_workspace_rejects_blank_name() -> None:
    with pytest.raises(
        ValueError,
        match="name cannot be blank",
    ):
        create_workspace(name="   ")


def test_workspace_rejects_name_above_maximum_length() -> None:
    with pytest.raises(
        ValueError,
        match="name cannot exceed",
    ):
        create_workspace(
            name="x" * (MAX_WORKSPACE_NAME_LENGTH + 1)
        )


def test_workspace_rejects_description_above_maximum_length() -> None:
    with pytest.raises(
        ValueError,
        match="description cannot exceed",
    ):
        create_workspace(
            description=(
                "x"
                * (
                    MAX_WORKSPACE_DESCRIPTION_LENGTH
                    + 1
                )
            )
        )


def test_workspace_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="created_at must be timezone-aware",
    ):
        create_workspace(
            created_at=datetime(2026, 9, 23, 12, 0)
        )


def test_workspace_rejects_updated_time_before_creation() -> None:
    with pytest.raises(
        ValueError,
        match="updated_at cannot precede created_at",
    ):
        create_workspace(
            updated_at=CREATED_AT - timedelta(seconds=1)
        )


def test_active_workspace_rejects_archive_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="active workspace cannot have archived_at",
    ):
        create_workspace(
            archived_at=CREATED_AT,
        )


def test_archived_workspace_requires_archive_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="archived workspace must have archived_at",
    ):
        create_workspace(
            status=WorkspaceStatus.ARCHIVED,
        )


def test_archived_workspace_is_valid_with_archive_timestamp() -> None:
    workspace = create_workspace(
        status=WorkspaceStatus.ARCHIVED,
        archived_at=CREATED_AT + timedelta(hours=1),
        updated_at=CREATED_AT + timedelta(hours=1),
    )

    assert workspace.is_available is False
    assert workspace.archived_at == (
        CREATED_AT + timedelta(hours=1)
    )


def test_deletion_requested_workspace_requires_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "deletion-requested workspace must have "
            "deletion_requested_at"
        ),
    ):
        create_workspace(
            status=WorkspaceStatus.DELETION_REQUESTED,
        )


def test_workspace_rejects_nonpositive_version() -> None:
    with pytest.raises(
        ValueError,
        match="version must be at least 1",
    ):
        create_workspace(version=0)
