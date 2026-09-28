"""PostgreSQL-backed integration tests for workspace use cases."""

import os
import subprocess
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import TracebackType
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql

from extensible_ai_workspace.workspace.application import (
    WorkspaceService,
    WorkspaceUnavailable,
)
from extensible_ai_workspace.workspace.domain import Workspace
from extensible_ai_workspace.workspace.infrastructure import (
    PostgresWorkspaceUnitOfWork,
)

ALEMBIC_CONFIG = Path(__file__).parents[1] / "alembic.ini"

ADMIN_DATABASE_URL = os.environ.get(
    "AIW_TEST_ADMIN_DATABASE_URL",
    "postgresql://app:development@127.0.0.1:5433/postgres",
)

OWNER_A_ID = UUID(
    "01990000-0000-7000-8000-000000000701"
)
OWNER_B_ID = UUID(
    "01990000-0000-7000-8000-000000000702"
)

WORKSPACE_A1_ID = UUID(
    "01990000-0000-7000-8000-000000000711"
)
WORKSPACE_A2_ID = UUID(
    "01990000-0000-7000-8000-000000000712"
)
WORKSPACE_B1_ID = UUID(
    "01990000-0000-7000-8000-000000000713"
)

BASE_TIME = datetime(
    2026,
    9,
    24,
    12,
    0,
    tzinfo=UTC,
)


@pytest.mark.integration
def test_workspace_application_persists_and_reopens_owned_workspaces() -> None:
    with TemporaryDatabase(
        "workspace_application"
    ) as database_url:
        _insert_user(
            database_url=database_url,
            user_id=OWNER_A_ID,
            display_name="Owner A",
        )
        _insert_user(
            database_url=database_url,
            user_id=OWNER_B_ID,
            display_name="Owner B",
        )

        workspace_a1 = _create_workspace_through_service(
            database_url=database_url,
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Owner A First Workspace",
            description="First persistent workspace.",
            current_time=BASE_TIME,
        )
        workspace_a2 = _create_workspace_through_service(
            database_url=database_url,
            workspace_id=WORKSPACE_A2_ID,
            owner_user_id=OWNER_A_ID,
            name="Owner A Second Workspace",
            description=None,
            current_time=BASE_TIME + timedelta(minutes=1),
        )
        workspace_b1 = _create_workspace_through_service(
            database_url=database_url,
            workspace_id=WORKSPACE_B1_ID,
            owner_user_id=OWNER_B_ID,
            name="Owner B Workspace",
            description="Unavailable to Owner A.",
            current_time=BASE_TIME + timedelta(minutes=2),
        )

        reopened_service = _create_workspace_service(
            database_url=database_url,
            workspace_id=uuid4(),
            current_time=BASE_TIME + timedelta(minutes=3),
        )

        listed_for_owner_a = reopened_service.list(
            owner_user_id=OWNER_A_ID
        )

        assert listed_for_owner_a == (
            workspace_a2,
            workspace_a1,
        )
        assert workspace_b1 not in listed_for_owner_a

        reopened_a1 = reopened_service.get(
            owner_user_id=OWNER_A_ID,
            workspace_id=WORKSPACE_A1_ID,
        )

        assert reopened_a1 == workspace_a1

        with pytest.raises(
            WorkspaceUnavailable,
            match="workspace is unavailable",
        ):
            reopened_service.get(
                owner_user_id=OWNER_A_ID,
                workspace_id=WORKSPACE_B1_ID,
            )

        with pytest.raises(
            WorkspaceUnavailable,
            match="workspace is unavailable",
        ):
            reopened_service.get(
                owner_user_id=OWNER_A_ID,
                workspace_id=uuid4(),
            )

        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    owner_user_id,
                    name,
                    status
                FROM workspace.workspaces
                ORDER BY created_at, id
                """
            ).fetchall()

        assert rows == [
            (
                WORKSPACE_A1_ID,
                OWNER_A_ID,
                "Owner A First Workspace",
                "ACTIVE",
            ),
            (
                WORKSPACE_A2_ID,
                OWNER_A_ID,
                "Owner A Second Workspace",
                "ACTIVE",
            ),
            (
                WORKSPACE_B1_ID,
                OWNER_B_ID,
                "Owner B Workspace",
                "ACTIVE",
            ),
        ]


def _create_workspace_through_service(
    *,
    database_url: str,
    workspace_id: UUID,
    owner_user_id: UUID,
    name: str,
    description: str | None,
    current_time: datetime,
) -> Workspace:
    """Create one workspace through the application service."""

    service = _create_workspace_service(
        database_url=database_url,
        workspace_id=workspace_id,
        current_time=current_time,
    )

    return service.create(
        owner_user_id=owner_user_id,
        name=name,
        description=description,
    )


def _create_workspace_service(
    *,
    database_url: str,
    workspace_id: UUID,
    current_time: datetime,
) -> WorkspaceService:
    """Create a PostgreSQL-backed deterministic workspace service."""

    unit_of_work_factory = partial(
        PostgresWorkspaceUnitOfWork,
        database_url,
    )

    return WorkspaceService(
        unit_of_work_factory=unit_of_work_factory,
        clock=lambda: current_time,
        identifier_generator=lambda: workspace_id,
    )


class TemporaryDatabase:
    """Create and remove one isolated migrated PostgreSQL database."""

    def __init__(self, prefix: str) -> None:
        self.database_name = f"aiw_{prefix}_{uuid4().hex}"
        self.database_url = (
            "postgresql://app:development@127.0.0.1:5433/"
            f"{self.database_name}"
        )

    def __enter__(self) -> str:
        _create_database(self.database_name)
        _run_alembic(
            database_url=self.database_url,
            command="upgrade",
            revision="head",
        )

        return self.database_url

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _drop_database(self.database_name)


def _insert_user(
    *,
    database_url: str,
    user_id: UUID,
    display_name: str,
) -> None:
    """Insert an active user required by the workspace foreign key."""

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            INSERT INTO iam.users (
                id,
                status,
                display_name,
                primary_email,
                created_at,
                updated_at,
                disabled_at,
                deletion_requested_at,
                version
            )
            VALUES (
                %s,
                'ACTIVE',
                %s,
                NULL,
                %s,
                %s,
                NULL,
                NULL,
                1
            )
            """,
            (
                user_id,
                display_name,
                BASE_TIME,
                BASE_TIME,
            ),
        )


def _create_database(database_name: str) -> None:
    """Create one temporary PostgreSQL database."""

    with psycopg.connect(
        ADMIN_DATABASE_URL,
        autocommit=True,
    ) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(database_name)
            )
        )


def _drop_database(database_name: str) -> None:
    """Remove one temporary PostgreSQL database."""

    with psycopg.connect(
        ADMIN_DATABASE_URL,
        autocommit=True,
    ) as admin_connection:
        admin_connection.execute(
            sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(
                sql.Identifier(database_name)
            )
        )


def _run_alembic(
    *,
    database_url: str,
    command: str,
    revision: str,
) -> None:
    """Run one Alembic command against a temporary database."""

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
