"""Application service for workspace use cases."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid7

from extensible_ai_workspace.workspace.application.errors import (
    WorkspaceUnavailable,
)
from extensible_ai_workspace.workspace.application.ports import (
    WorkspaceUnitOfWorkFactory,
)
from extensible_ai_workspace.workspace.domain import (
    Workspace,
    WorkspaceStatus,
)

Clock = Callable[[], datetime]
IdentifierGenerator = Callable[[], UUID]


class WorkspaceService:
    """Create and query workspaces for an authenticated owner."""

    def __init__(
        self,
        *,
        unit_of_work_factory: WorkspaceUnitOfWorkFactory,
        clock: Clock = lambda: datetime.now(UTC),
        identifier_generator: IdentifierGenerator = uuid7,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._identifier_generator = identifier_generator

    def create(
        self,
        *,
        owner_user_id: UUID,
        name: str,
        description: str | None = None,
    ) -> Workspace:
        """Create and persist an active workspace."""

        current_time = self._current_time()

        workspace = Workspace(
            id=self._identifier_generator(),
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            status=WorkspaceStatus.ACTIVE,
            created_at=current_time,
            updated_at=current_time,
            archived_at=None,
            deletion_requested_at=None,
            version=1,
        )

        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.workspaces.add(workspace)
            unit_of_work.commit()

        return workspace

    def get(
        self,
        *,
        owner_user_id: UUID,
        workspace_id: UUID,
    ) -> Workspace:
        """Return an active workspace owned by the caller."""

        with self._unit_of_work_factory() as unit_of_work:
            workspace = unit_of_work.workspaces.get_for_owner(
                workspace_id=workspace_id,
                owner_user_id=owner_user_id,
            )

        if workspace is None:
            raise WorkspaceUnavailable(
                "The workspace is unavailable."
            )

        return workspace

    def list(
        self,
        *,
        owner_user_id: UUID,
    ) -> Sequence:
        """Return the caller's active workspaces in stable order."""

        with self._unit_of_work_factory() as unit_of_work:
            workspaces = unit_of_work.workspaces.list_for_owner(
                owner_user_id
            )

        return tuple(workspaces)

    def _current_time(self) -> datetime:
        """Return one timezone-aware application timestamp."""

        current_time = self._clock()

        if (
            current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise ValueError(
                "The application clock must return "
                "a timezone-aware timestamp."
            )

        return current_time
