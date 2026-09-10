"""PostgreSQL infrastructure boundary."""

from extensible_ai_workspace.database.health import check_database_connection

__all__ = ["check_database_connection"]
