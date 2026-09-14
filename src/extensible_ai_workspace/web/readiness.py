"""Web runtime readiness checks."""

from collections.abc import Callable

from extensible_ai_workspace.database import check_database_schema

ReadinessCheck = Callable[[], bool]


def default_readiness_check() -> bool:
    """Report readiness for the current in-process foundation."""

    return True


def create_database_readiness_check(
    database_url: str,
) -> ReadinessCheck:
    """Create a database and schema readiness check."""

    def database_is_ready() -> bool:
        return check_database_schema(database_url)

    return database_is_ready
