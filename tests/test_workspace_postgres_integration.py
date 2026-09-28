"""PostgreSQL integration tests for workspace persistence."""

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql

from extensible_ai_workspace.workspace.domain import (
    Workspace,
    WorkspaceStatus,
)
from extensible_ai_workspace.workspace.infrastructure import (
    PostgresWorkspaceUnitOfWork,
    WorkspacePersistenceConflict,
)

ALEMBIC_CONFIG = Path(__file__).parents[1] / "alembic.ini"

ADMIN_DATABASE_URL = os.environ.get(
    "AIW_TEST_ADMIN_DATABASE_URL",
    "postgresql://app:development@127.0.0.1:5433/postgres",
)

OWNER_A_ID = UUID(
    "01990000-0000-7000-8000-000000000501"
)
OWNER_B_ID = UUID(
    "01990000-0000-7000-8000-000000000502"
)

WORKSPACE_A1_ID = UUID(
    "01990000-0000-7000-8000-000000000511"
)
WORKSPACE_A2_ID = UUID(
    "01990000-0000-7000-8000-000000000512"
)
WORKSPACE_B1_ID = UUID(
    "01990000-0000-7000-8000-000000000513"
)

CREATED_AT = datetime(
    2026,
    9,
    23,
    12,
    0,
    tzinfo=UTC,
)


@pytest.mark.integration
def test_workspace_repository_round_trips_owned_workspace() -> None:
    with TemporaryDatabase(
        "workspace_round_trip"
    ) as database_url:
        _insert_user(database_url, OWNER_A_ID)

        workspace = _create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Research Workspace",
            created_at=CREATED_AT,
        )

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.workspaces.add(workspace)
            unit_of_work.commit()

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            loaded = unit_of_work.workspaces.get_for_owner(
                workspace_id=WORKSPACE_A1_ID,
                owner_user_id=OWNER_A_ID,
            )

        assert loaded == workspace


@pytest.mark.integration
def test_workspace_repository_enforces_owner_scope() -> None:
    with TemporaryDatabase(
        "workspace_ownership"
    ) as database_url:
        _insert_user(database_url, OWNER_A_ID)
        _insert_user(database_url, OWNER_B_ID)

        workspace = _create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Owner A Workspace",
            created_at=CREATED_AT,
        )

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.workspaces.add(workspace)
            unit_of_work.commit()

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            unavailable = (
                unit_of_work.workspaces.get_for_owner(
                    workspace_id=WORKSPACE_A1_ID,
                    owner_user_id=OWNER_B_ID,
                )
            )

        assert unavailable is None


@pytest.mark.integration
def test_workspace_repository_lists_only_owner_in_stable_order() -> None:
    with TemporaryDatabase(
        "workspace_listing"
    ) as database_url:
        _insert_user(database_url, OWNER_A_ID)
        _insert_user(database_url, OWNER_B_ID)

        workspace_a1 = _create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Older Workspace",
            created_at=CREATED_AT,
        )
        workspace_a2 = _create_workspace(
            workspace_id=WORKSPACE_A2_ID,
            owner_user_id=OWNER_A_ID,
            name="Newer Workspace",
            created_at=CREATED_AT + timedelta(minutes=1),
        )
        workspace_b1 = _create_workspace(
            workspace_id=WORKSPACE_B1_ID,
            owner_user_id=OWNER_B_ID,
            name="Different Owner",
            created_at=CREATED_AT + timedelta(minutes=2),
        )

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.workspaces.add(workspace_a1)
            unit_of_work.workspaces.add(workspace_a2)
            unit_of_work.workspaces.add(workspace_b1)
            unit_of_work.commit()

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            listed = list(
                unit_of_work.workspaces.list_for_owner(
                    OWNER_A_ID
                )
            )

        assert listed == [
            workspace_a2,
            workspace_a1,
        ]


@pytest.mark.integration
def test_workspace_repository_uses_id_as_ordering_tiebreaker() -> None:
    with TemporaryDatabase(
        "workspace_tiebreaker"
    ) as database_url:
        _insert_user(database_url, OWNER_A_ID)

        workspace_a1 = _create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="First Identifier",
            created_at=CREATED_AT,
        )
        workspace_a2 = _create_workspace(
            workspace_id=WORKSPACE_A2_ID,
            owner_user_id=OWNER_A_ID,
            name="Second Identifier",
            created_at=CREATED_AT,
        )

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.workspaces.add(workspace_a1)
            unit_of_work.workspaces.add(workspace_a2)
            unit_of_work.commit()

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            listed = list(
                unit_of_work.workspaces.list_for_owner(
                    OWNER_A_ID
                )
            )

        assert listed == [
            workspace_a2,
            workspace_a1,
        ]


@pytest.mark.integration
def test_workspace_unit_of_work_rolls_back_without_commit() -> None:
    with TemporaryDatabase(
        "workspace_rollback"
    ) as database_url:
        _insert_user(database_url, OWNER_A_ID)

        workspace = _create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Rolled Back Workspace",
            created_at=CREATED_AT,
        )

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.workspaces.add(workspace)

        with PostgresWorkspaceUnitOfWork(
            database_url
        ) as unit_of_work:
            loaded = unit_of_work.workspaces.get_for_owner(
                workspace_id=WORKSPACE_A1_ID,
                owner_user_id=OWNER_A_ID,
            )

        assert loaded is None


@pytest.mark.integration
def test_workspace_requires_persisted_owner() -> None:
    with TemporaryDatabase(
        "workspace_foreign_key"
    ) as database_url:
        workspace = _create_workspace(
            workspace_id=WORKSPACE_A1_ID,
            owner_user_id=OWNER_A_ID,
            name="Invalid Owner Workspace",
            created_at=CREATED_AT,
        )

        with pytest.raises(WorkspacePersistenceConflict):
            with PostgresWorkspaceUnitOfWork(
                database_url
            ) as unit_of_work:
                unit_of_work.workspaces.add(workspace)
                unit_of_work.commit()


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
            self.database_url,
            "upgrade",
            "head",
        )

        return self.database_url

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _drop_database(self.database_name)


def _create_workspace(
    *,
    workspace_id: UUID,
    owner_user_id: UUID,
    name: str,
    created_at: datetime,
) -> Workspace:
    return Workspace(
        id=workspace_id,
        owner_user_id=owner_user_id,
        name=name,
        description=None,
        status=WorkspaceStatus.ACTIVE,
        created_at=created_at,
        updated_at=created_at,
    )


def _insert_user(
    database_url: str,
    user_id: UUID,
) -> None:
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
                f"Test User {user_id}",
                CREATED_AT,
                CREATED_AT,
            ),
        )


def _create_database(database_name: str) -> None:
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
