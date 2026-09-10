"""PostgreSQL connectivity checks."""

import psycopg
from psycopg import Connection


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


def _execute_connectivity_query(connection: Connection[tuple]) -> None:
    """Execute the minimal PostgreSQL connectivity query."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
