"""PostgreSQL infrastructure boundary."""

from extensible_ai_workspace.database.health import (
    SUPPORTED_SCHEMA_REVISIONS,
    check_database_connection,
    check_database_schema,
)

__all__ = [
    "SUPPORTED_SCHEMA_REVISIONS",
    "check_database_connection",
    "check_database_schema",
]
