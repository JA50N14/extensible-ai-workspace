"""Unit tests for workspace application use cases."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID

import pytest

from extensible_ai_workspace.workspace.application import (
    WorkspaceService,
    WorkspaceUnavailable,
)
from extensible_ai_workspace.workspace.domain import (
    Workspace,
    WorkspaceStatus,
)

OWNER_A_ID = UUID(
    "01990000-0000-7000-8000-000000000601"
)
OWNER_B_ID = UUID(
    "01990000-0000-7000-8000-000000000602"
)

WORKSPACE_A1_ID = UUID(
    "01990000-0000-7000-8000-000000000611"
)
WORKSPACE_A2_ID = UUID(
    "01990000-0000-7000-8000-000000000612"
)
WORKSPACE_B1_ID = UUID(
    "01990000-0000-7000-8000-000000000613"
)

NOW = datetime(
    2026,
    9,
    24,
    12,
    0,
    tzinfo=UTC,
)


class FakeWorkspaceRepository:
    """In-memory repository with production-like ownership filtering."""

    def __init__(self) -> None:
        self.records: dict[UUID, Workspace] = {}

    def add(
        self,
        workspace: Workspace,
    ) -> None:
        """Store a workspace by identifier."""

        self.records[workspace.id] = workspace

    def get_for_owner(
        self,
        *,
        workspace_id: UUID,
        owner_user_id: UUID,
    ) -> Workspace | None:
        """Return an active workspace owned by the supplied user."""

        workspace = self.records.get(workspace_id)

        if workspace is None:
            return None

        if workspace.owner_user_id != owner_user_id:
            return None

        if workspace.status is not WorkspaceStatus.ACTIVE:
            return None

        return workspace

    def list_for_owner(
        self,
        owner_user_id: UUID,
    ) -> list:
        """Return active owned workspaces in stable newest-first order."""

        owned_workspaces = [
            workspace
            for workspace in self.records.values()
            if (
                workspace.owner_user_id == owner_user_id
                and workspace.status is WorkspaceStatus.ACTIVE
            )
        ]

        return sorted(
            owned_workspaces,
            key=lambda workspace: (
                workspace.created_at,
                workspace.id,
            ),
            reverse=True,
        )


class FakeWorkspaceUnitOfWork:
    """Test transaction boundary for workspace use cases."""

    def __init__(
        self,
        repository: FakeWorkspaceRepository,
    ) -> None:
        self.workspaces = repository
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeWorkspaceUnitOfWork":
        """Enter the fake transaction boundary."""

        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Record rollback when work exits without a commit."""

        if exception_type is not None or not self.committed:
            self.rollback()

    def commit(self) -> None:
        """Record that the use case committed its changes."""

        self.committed = True
        self.rolled_back = False

    def rollback(self) -> None:
        """Record that the use case rolled back its changes."""

        self.committed = False
        self.rolled_back = True


class TrackingUnitOfWorkFactory:
    """Create fake units of work and retain them for assertions."""

    def __init__(
        self,
        repository: FakeWorkspaceRepository,
    ) -> None:
        self.repository = repository
        self.created: list[FakeWorkspaceUnitOfWork] = []

    def __call__(self) -> FakeWorkspaceUnitOfWork:
        """Create one fresh fake Unit of Work."""

        unit_of_work = FakeWorkspaceUnitOfWork(
            self.repository
        )
        self.created.append(unit_of_work)

        return unit_of_work


def create_workspace(
    *,
    workspace_id: UUID,
    owner_user_id: UUID,
    name: str,
    created_at: datetime,
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE,
) -> Workspace:
    """Create a workspace fixture with valid lifecycle timestamps."""

    archived_at: datetime | None = None
    updated_at = created_at

    if status is WorkspaceStatus.ARCHIVED:
        archived_at = created_at + timedelta(minutes=1)
        updated_at = archived_at

    return Workspace(
        id=workspace_id,
        owner_user_id=owner_user_id,
        name=name,
        description=None,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        archived_at=archived_at,
        deletion_requested_at=None,
        version=1,
    )


def create_service(
    repository: FakeWorkspaceRepository,
    *,
    identifier: UUID = WORKSPACE_A1_ID,
    current_time: datetime = NOW,
) -> tuple[
    WorkspaceService,
    TrackingUnitOfWorkFactory,
]:
    """Create a deterministic workspace service for testing."""

    unit_of_work_factory = TrackingUnitOfWorkFactory(
        repository
    )
    service = WorkspaceService(
        unit_of_work_factory=unit_of_work_factory,
        clock=lambda: current_time,
        identifier_generator=lambda: identifier,
    )

    return service, unit_of_work_factory


def test_create_assigns_server_controlled_fields() -> None:
    repository = FakeWorkspaceRepository()
    service, unit_of_work_factory = create_service(
        repository
    )

    workspace = service.create(
        owner_user_id=OWNER_A_ID,
        name="  Research Workspace  ",
        description="  Initial research.  ",
    )

    assert workspace.id == WORKSPACE_A1_ID
    assert workspace.owner_user_id == OWNER_A_ID
    assert workspace.name == "Research Workspace"
    assert workspace.description == "Initial research."
    assert workspace.status is WorkspaceStatus.ACTIVE
    assert workspace.created_at == NOW
    assert workspace.updated_at == NOW
    assert workspace.archived_at is None
    assert workspace.deletion_requested_at is None
    assert workspace.version == 1

    assert repository.records[workspace.id] == workspace
    assert len(unit_of_work_factory.created) == 1
    assert unit_of_work_factory.created[0].committed is True
    assert unit_of_work_factory.created[0].rolled_back is False


def test_create_rejects_invalid_workspace_before_persistence() -> None:
    repository = FakeWorkspaceRepository()
    service, unit_of_work_factory = create_service(
        repository
    )

    with pytest.raises(
        ValueError,
        match="name cannot be blank",
    ):
        service.create(
            owner_user_id=OWNER_A_ID,
            name="   ",
        )

    assert repository.records == {}
    assert unit_of_work_factory.created == []


def test_get_returns_owned_workspace() -> None:
    repository = FakeWorkspaceRepository()
    workspace = create_workspace(
        workspace_id=WORKSPACE_A1_ID,
        owner_user_id=OWNER_A_ID,
        name="Research Workspace",
        created_at=NOW,
    )
    repository.add(workspace)

    service, unit_of_work_factory = create_service(
        repository
    )

    result = service.get(
        owner_user_id=OWNER_A_ID,
        workspace_id=WORKSPACE_A1_ID,
    )

    assert result == workspace
    assert len(unit_of_work_factory.created) == 1
    assert unit_of_work_factory.created[0].committed is False
    assert unit_of_work_factory.created[0].rolled_back is True


def test_get_treats_missing_workspace_as_unavailable() -> None:
    repository = FakeWorkspaceRepository()
    service, _ = create_service(repository)

    with pytest.raises(
        WorkspaceUnavailable,
        match="workspace is unavailable",
    ):
        service.get(
            owner_user_id=OWNER_A_ID,
            workspace_id=WORKSPACE_A1_ID,
        )


def test_get_treats_other_owners_workspace_as_unavailable() -> None:
    repository = FakeWorkspaceRepository()
    repository.add(
        create_workspace(
            workspace_id=WORKSPACE_B1_ID,
            owner_user_id=OWNER_B_ID,
            name="Owner B Workspace",
            created_at=NOW,
        )
    )

    service, _ = create_service(repository)

    with pytest.raises(
        WorkspaceUnavailable,
        match="workspace is unavailable",
    ):
        service.get(
            owner_user_id=OWNER_A_ID,
            workspace_id=WORKSPACE_B1_ID,
        )


def test_get_treats_nonactive_workspace_as_unavailable() -> None:
    repository = FakeWorkspaceRepository()
    repository.add(
        create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Archived Workspace",
            created_at=NOW,
            status=WorkspaceStatus.ARCHIVED,
        )
    )

    service, _ = create_service(repository)

    with pytest.raises(
        WorkspaceUnavailable,
        match="workspace is unavailable",
    ):
        service.get(
            owner_user_id=OWNER_A_ID,
            workspace_id=WORKSPACE_A1_ID,
        )


def test_list_returns_only_owned_active_workspaces_in_order() -> None:
    repository = FakeWorkspaceRepository()

    workspace_a1 = create_workspace(
        workspace_id=WORKSPACE_A1_ID,
        owner_user_id=OWNER_A_ID,
        name="Older Workspace",
        created_at=NOW,
    )
    workspace_a2 = create_workspace(
        workspace_id=WORKSPACE_A2_ID,
        owner_user_id=OWNER_A_ID,
        name="Newer Workspace",
        created_at=NOW + timedelta(minutes=1),
    )
    workspace_b1 = create_workspace(
        workspace_id=WORKSPACE_B1_ID,
        owner_user_id=OWNER_B_ID,
        name="Different Owner",
        created_at=NOW + timedelta(minutes=2),
    )

    repository.add(workspace_a1)
    repository.add(workspace_a2)
    repository.add(workspace_b1)

    service, unit_of_work_factory = create_service(
        repository
    )

    result = service.list(
        owner_user_id=OWNER_A_ID
    )

    assert result == (
        workspace_a2,
        workspace_a1,
    )
    assert isinstance(result, tuple)
    assert len(unit_of_work_factory.created) == 1
    assert unit_of_work_factory.created[0].committed is False
    assert unit_of_work_factory.created[0].rolled_back is True


def test_list_uses_identifier_as_timestamp_tiebreaker() -> None:
    repository = FakeWorkspaceRepository()

    workspace_a1 = create_workspace(
        workspace_id=WORKSPACE_A1_ID,
        owner_user_id=OWNER_A_ID,
        name="Lower Identifier",
        created_at=NOW,
    )
    workspace_a2 = create_workspace(
        workspace_id=WORKSPACE_A2_ID,
        owner_user_id=OWNER_A_ID,
        name="Higher Identifier",
        created_at=NOW,
    )

    repository.add(workspace_a1)
    repository.add(workspace_a2)

    service, _ = create_service(repository)

    result = service.list(
        owner_user_id=OWNER_A_ID
    )

    assert result == (
        workspace_a2,
        workspace_a1,
    )


def test_list_returns_empty_tuple_for_owner_without_workspaces() -> None:
    repository = FakeWorkspaceRepository()
    service, _ = create_service(repository)

    result = service.list(
        owner_user_id=OWNER_A_ID
    )

    assert result == ()
    assert isinstance(result, tuple)


def test_service_rejects_naive_clock_before_opening_unit_of_work() -> None:
    repository = FakeWorkspaceRepository()
    service, unit_of_work_factory = create_service(
        repository,
        current_time=datetime(2026, 9, 24, 12, 0),
    )

    with pytest.raises(
        ValueError,
        match=(
            "application clock must return "
            "a timezone-aware timestamp"
        ),
    ):
        service.create(
            owner_user_id=OWNER_A_ID,
            name="Research Workspace",
        )

    assert unit_of_work_factory.created == []
