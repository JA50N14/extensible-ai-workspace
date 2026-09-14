from unittest.mock import MagicMock

import psycopg
import pytest

from extensible_ai_workspace.database import check_database_connection

TEST_DATABASE_URL = (
    "postgresql://app:development@localhost:5432/"
    "extensible_ai_workspace"
)


def test_database_connection_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    connect = MagicMock(return_value=connection_context)

    monkeypatch.setattr(
        "extensible_ai_workspace.database.health.psycopg.connect",
        connect,
    )

    result = check_database_connection(TEST_DATABASE_URL)

    assert result is True
    connect.assert_called_once_with(
        TEST_DATABASE_URL,
        connect_timeout=2,
    )

    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.assert_called_once_with("SELECT 1")
    cursor.fetchone.assert_called_once_with()


def test_database_connection_failure_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect = MagicMock(
        side_effect=psycopg.OperationalError("Connection unavailable")
    )

    monkeypatch.setattr(
        "extensible_ai_workspace.database.health.psycopg.connect",
        connect,
    )

    result = check_database_connection(TEST_DATABASE_URL)

    assert result is False


def test_database_schema_accepts_supported_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("0001",)

    connect = MagicMock(return_value=connection_context)

    monkeypatch.setattr(
        "extensible_ai_workspace.database.health.psycopg.connect",
        connect,
    )

    from extensible_ai_workspace.database import check_database_schema

    result = check_database_schema(TEST_DATABASE_URL)

    assert result is True
    cursor.execute.assert_called_once_with(
        "SELECT version_num FROM alembic_version"
    )


def test_database_schema_rejects_unsupported_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("9999",)

    connect = MagicMock(return_value=connection_context)

    monkeypatch.setattr(
        "extensible_ai_workspace.database.health.psycopg.connect",
        connect,
    )

    from extensible_ai_workspace.database import check_database_schema

    result = check_database_schema(TEST_DATABASE_URL)

    assert result is False


def test_database_schema_rejects_missing_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None

    connect = MagicMock(return_value=connection_context)

    monkeypatch.setattr(
        "extensible_ai_workspace.database.health.psycopg.connect",
        connect,
    )

    from extensible_ai_workspace.database import check_database_schema

    result = check_database_schema(TEST_DATABASE_URL)

    assert result is False


def test_database_schema_failure_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect = MagicMock(
        side_effect=psycopg.OperationalError("Database unavailable")
    )

    monkeypatch.setattr(
        "extensible_ai_workspace.database.health.psycopg.connect",
        connect,
    )

    from extensible_ai_workspace.database import check_database_schema

    result = check_database_schema(TEST_DATABASE_URL)

    assert result is False
