"""PostgreSQL-backed integration test for local authentication."""

import os
import subprocess
from functools import partial
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from extensible_ai_workspace.identity.application import (
    TrustedLocalIdentity,
    TrustedLocalSessionService,
)
from extensible_ai_workspace.identity.infrastructure import (
    PostgresIdentityUnitOfWork,
)
from extensible_ai_workspace.web import create_app
from extensible_ai_workspace.web.auth import SESSION_COOKIE_NAME

ALEMBIC_CONFIG = Path(__file__).parents[1] / "alembic.ini"

ADMIN_DATABASE_URL = os.environ.get(
    "AIW_TEST_ADMIN_DATABASE_URL",
    "postgresql://app:development@127.0.0.1:5433/postgres",
)

PUBLIC_ORIGIN = "http://127.0.0.1:8000"


@pytest.mark.integration
def test_trusted_local_session_survives_application_recreation() -> None:
    database_name = f"aiw_auth_test_{uuid4().hex}"
    database_url = (
        "postgresql://app:development@127.0.0.1:5433/"
        f"{database_name}"
    )

    _create_database(database_name)

    try:
        _run_alembic(database_url, "upgrade", "head")

        first_client = _create_client(database_url)

        login_response = first_client.get("/auth/login")

        assert login_response.status_code == 200

        login_body = login_response.json()
        csrf_token = login_body["csrf_token"]
        session_token = first_client.cookies.get(
            SESSION_COOKIE_NAME
        )

        assert session_token is not None
        assert session_token not in login_response.text
        assert login_body["user"]["display_name"] == "Local User"

        with psycopg.connect(database_url) as connection:
            persisted_counts = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM iam.users),
                    (
                        SELECT count(*)
                        FROM iam.external_identities
                    ),
                    (SELECT count(*) FROM iam.sessions)
                """
            ).fetchone()

            persisted_session = connection.execute(
                """
                SELECT
                    session_token_hash,
                    csrf_verifier,
                    revoked_at
                FROM iam.sessions
                """
            ).fetchone()

        assert persisted_counts == (1, 1, 1)
        assert persisted_session is not None
        assert session_token.encode() not in persisted_session
        assert csrf_token.encode() not in persisted_session
        assert persisted_session[2] is None

        recreated_client = _create_client(database_url)
        recreated_client.cookies.set(
            SESSION_COOKIE_NAME,
            session_token,
        )

        inspection_response = recreated_client.get(
            "/auth/session"
        )

        assert inspection_response.status_code == 200
        inspection_body = inspection_response.json()

        assert (
            inspection_body["user"]["display_name"]
            == "Local User"
        )
        assert inspection_body["identity"] == {
            "provider_type": "LOCAL_TRUSTED",
            "issuer": "extensible-ai-workspace-local",
        }
        assert "csrf_token" not in inspection_body
        assert session_token not in inspection_response.text
        assert csrf_token not in inspection_response.text

        logout_response = recreated_client.post(
            "/auth/logout",
            headers={
                "Origin": PUBLIC_ORIGIN,
                "X-CSRF-Token": csrf_token,
            },
        )

        assert logout_response.status_code == 200
        assert logout_response.json() == {
            "status": "logged_out"
        }

        with psycopg.connect(database_url) as connection:
            revoked_at = connection.execute(
                """
                SELECT revoked_at
                FROM iam.sessions
                """
            ).fetchone()

        assert revoked_at is not None
        assert revoked_at[0] is not None

        stale_client = _create_client(database_url)
        stale_client.cookies.set(
            SESSION_COOKIE_NAME,
            session_token,
        )

        stale_response = stale_client.get("/auth/session")

        assert stale_response.status_code == 401
        assert stale_response.json()["code"] == "SESSION_INVALID"
    finally:
        _drop_database(database_name)


def _create_client(
    database_url: str,
) -> TestClient:
    unit_of_work_factory = partial(
        PostgresIdentityUnitOfWork,
        database_url,
    )
    session_service_factory = partial(
        TrustedLocalSessionService,
        unit_of_work_factory=unit_of_work_factory,
        trusted_identity=TrustedLocalIdentity(
            issuer="extensible-ai-workspace-local",
            subject="local-user",
            display_name="Local User",
        ),
    )
    app = create_app(
        session_service_factory=session_service_factory,
        public_origin=PUBLIC_ORIGIN,
        secure_cookie=False,
    )

    return TestClient(app)


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
