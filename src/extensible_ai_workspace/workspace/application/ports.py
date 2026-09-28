"""Application ports required by workspace use cases."""

from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Protocol
from uuid import UUID

from extensible_ai_workspace.workspace.domain import Workspace


class WorkspaceRepository(Protocol):
    """Persistence operations required by workspace use cases."""

    def add(
        self,
        workspace: Workspace,
    ) -> None:
        """Persist a new workspace."""

        ...

    def get_for_owner(
        self,
        *,
        workspace_id: UUID,
        owner_user_id: UUID,
    ) -> Workspace | None:
        """Return an owned workspace when it is available."""

        ...

    def list_for_owner(
        self,
        owner_user_id: UUID,
    ) -> Sequence:
        """Return owned workspaces in stable newest-first order."""
        ...


class WorkspaceUnitOfWork(Protocol):
    """Transaction boundary for workspace use cases."""

    workspaces: WorkspaceRepository

    def __enter__(self) -> "WorkspaceUnitOfWork":
        """Enter the workspace transaction boundary."""

        ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the transaction and release its resources."""

        ...

    def commit(self) -> None:
        """Commit all changes performed in this unit of work."""

        ...

    def rollback(self) -> None:
        """Discard all uncommitted changes."""

        ...


WorkspaceUnitOfWorkFactory = Callable[[], WorkspaceUnitOfWork]
