"""Application failures for workspace use cases."""


class WorkspaceError(RuntimeError):
    """Base workspace application failure."""


class WorkspaceUnavailable(WorkspaceError):
    """The requested workspace is unavailable to the caller."""
