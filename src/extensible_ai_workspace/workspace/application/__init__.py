"""Workspace application boundary."""

from extensible_ai_workspace.workspace.application.errors import (
    WorkspaceError,
    WorkspaceUnavailable,
)
from extensible_ai_workspace.workspace.application.ports import (
    WorkspaceRepository,
    WorkspaceUnitOfWork,
    WorkspaceUnitOfWorkFactory,
)
from extensible_ai_workspace.workspace.application.service import (
    WorkspaceService,
)

__all__ = [
    "WorkspaceError",
    "WorkspaceRepository",
    "WorkspaceService",
    "WorkspaceUnavailable",
    "WorkspaceUnitOfWork",
    "WorkspaceUnitOfWorkFactory",
]
