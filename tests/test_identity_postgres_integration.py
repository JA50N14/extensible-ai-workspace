"""PostgreSQL integration tests for Identity and Access persistence."""

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql

from extensible_ai_workspace.identity.domain import (
    ApplicationSession,
    AuthenticationMethod,
    ExternalIdentity,
    IdentityProviderType,
    InternalUser,
    UserStatus,
)
from extensible_ai_workspace.identity.infrastructure import (
    PostgresIdentityUnitOfWork,
)

ALEMBIC_CONFIG = Path(__file__).parents[1] / "alembic.ini"

ADMIN_DATABASE_URL = os.environ.get(
    "AIW_TEST_ADMIN_DATABASE_URL",
    "postgresql://app:development@127.0.0.1:5433/postgres",
)

USER_ID = UUID("01990000-0000-7000-8000-000000000101")
IDENTITY_ID = UUID("01990000-0000-7000-8000-000000000102")
SESSION_ID = UUID("01990000-0000-7000-8000-000000000103")
CREATED_AT = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


@pytest.mark.integration
def test_identity_unit_of_work_persists_and_loads_session() -> None:
    database_name = f"aiw_identity_test_{uuid4().hex}"
    database_url = (
        "postgresql://app:development@127.0.0.1:5433/"
        f"{database_name}"
    )

    _create_database(database_name)

    try:
        _run_alembic(database_url, "upgrade", "head")

        user = InternalUser(
            id=USER_ID,
            status=UserStatus.ACTIVE,
            display_name="Local User",
            primary_email=None,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        identity = ExternalIdentity(
            id=IDENTITY_ID,
            user_id=USER_ID,
            provider_type=IdentityProviderType.LOCAL_TRUSTED,
            issuer="extensible-ai-workspace-local",
            subject="local-user",
            created_at=CREATED_AT,
        )
        session = ApplicationSession(
            id=SESSION_ID,
            user_id=USER_ID,
            external_identity_id=IDENTITY_ID,
            authentication_method=AuthenticationMethod.LOCAL_TRUSTED,
            session_token_hash=b"persisted-session-hash",
            csrf_verifier=b"persisted-csrf-verifier",
            created_at=CREATED_AT,
            last_activity_at=CREATED_AT,
            idle_expires_at=CREATED_AT + timedelta(minutes=30),
            absolute_expires_at=CREATED_AT + timedelta(hours=8),
            authenticated_at=CREATED_AT,
        )

        with PostgresIdentityUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.identities.add_user(user)
            unit_of_work.identities.add_external_identity(identity)
            unit_of_work.identities.add_session(session)
            unit_of_work.commit()

        with PostgresIdentityUnitOfWork(
            database_url
        ) as unit_of_work:
            loaded_identity = (
                unit_of_work.identities.get_external_identity(
                    provider_type=(
                        IdentityProviderType.LOCAL_TRUSTED
                    ),
                    issuer="extensible-ai-workspace-local",
                    subject="local-user",
                )
            )
            loaded_user = unit_of_work.identities.get_user(USER_ID)
            loaded_session = (
                unit_of_work.identities.get_session_by_token_hash(
                    b"persisted-session-hash"
                )
            )

        assert loaded_user == user
        assert loaded_identity == identity
        assert loaded_session == session
    finally:
        _drop_database(database_name)


@pytest.mark.integration
def test_identity_unit_of_work_rolls_back_without_commit() -> None:
    database_name = f"aiw_identity_rollback_{uuid4().hex}"
    database_url = (
        "postgresql://app:development@127.0.0.1:5433/"
        f"{database_name}"
    )

    _create_database(database_name)

    try:
        _run_alembic(database_url, "upgrade", "head")

        user = InternalUser(
            id=USER_ID,
            status=UserStatus.ACTIVE,
            display_name="Local User",
            primary_email=None,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )

        with PostgresIdentityUnitOfWork(
            database_url
        ) as unit_of_work:
            unit_of_work.identities.add_user(user)

        with PostgresIdentityUnitOfWork(
            database_url
        ) as unit_of_work:
            loaded_user = unit_of_work.identities.get_user(USER_ID)

        assert loaded_user is None
    finally:
        _drop_database(database_name)


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
