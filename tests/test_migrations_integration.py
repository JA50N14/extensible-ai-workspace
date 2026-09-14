"""PostgreSQL integration tests for Alembic migrations."""

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

ALEMBIC_CONFIG = Path(__file__).parents[1] / "alembic.ini"

ADMIN_DATABASE_URL = os.environ.get(
    "AIW_TEST_ADMIN_DATABASE_URL",
    "postgresql://app:development@127.0.0.1:5433/postgres",
)


@pytest.mark.integration
def test_initial_migration_upgrades_and_downgrades_clean_database() -> None:
    database_name = f"aiw_migration_test_{uuid4().hex}"
    database_url = (
        "postgresql://app:development@127.0.0.1:5433/"
        f"{database_name}"
    )

    with psycopg.connect(
        ADMIN_DATABASE_URL,
        autocommit=True,
    ) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(database_name)
            )
        )

    try:
        _run_alembic(database_url, "upgrade", "head")

        with psycopg.connect(database_url) as connection:
            revision = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            tables = connection.execute(
                """
                SELECT table_schema || '.' || table_name
                FROM information_schema.tables
                WHERE table_schema IN ('iam', 'workspace')
                  AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name
                """
            ).fetchall()

        assert revision == ("0001",)
        assert tables == [
            ("iam.external_identities",),
            ("iam.sessions",),
            ("iam.users",),
            ("workspace.workspaces",),
        ]

        _run_alembic(database_url, "downgrade", "base")

        with psycopg.connect(database_url) as connection:
            schemas = connection.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN ('iam', 'workspace')
                ORDER BY schema_name
                """
            ).fetchall()

        assert schemas == []
    finally:
        with psycopg.connect(
            ADMIN_DATABASE_URL,
            autocommit=True,
        ) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )


def _run_alembic(
    database_url: str,
    command: str,
    revision: str,
) -> None:
    environment = os.environ.copy()
    environment["AIW_DATABASE_URL"] = database_url

    subprocess.run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            str(ALEMBIC_CONFIG),
            command,
            revision,
        ],
        check=True,
        env=environment,
        cwd=ALEMBIC_CONFIG.parent,
    )
