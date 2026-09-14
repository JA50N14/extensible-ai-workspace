"""PostgreSQL connectivity and schema checks."""

import psycopg
from psycopg import Connection

SUPPORTED_SCHEMA_REVISIONS = frozenset({"0001"})


def check_database_connection(database_url: str) -> bool:
    """Return whether PostgreSQL accepts a simple query."""

    try:
        with psycopg.connect(
            database_url,
            connect_timeout=2,
        ) as connection:
            _execute_connectivity_query(connection)
    except psycopg.Error:
        return False

    return True


def check_database_schema(
    database_url: str,
    supported_revisions: frozenset[str] = SUPPORTED_SCHEMA_REVISIONS,
) -> bool:
    """Return whether the applied database revision is supported."""

    try:
        with psycopg.connect(
            database_url,
            connect_timeout=2,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT version_num FROM alembic_version"
                )
                row = cursor.fetchone()
    except psycopg.Error:
        return False

    return row is not None and row[0] in supported_revisions


def _execute_connectivity_query(connection: Connection[tuple]) -> None:
    """Execute the minimal PostgreSQL connectivity query."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
