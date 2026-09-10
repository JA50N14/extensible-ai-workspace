from unittest.mock import Mock

import pytest

from extensible_ai_workspace.config import RuntimeRole, Settings
from extensible_ai_workspace.runtime import run_web

TEST_DATABASE_URL = (
    "postgresql://app:development@localhost:5432/"
    "extensible_ai_workspace"
)


def test_run_web_starts_database_ready_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        runtime_role=RuntimeRole.WEB,
        database_url=TEST_DATABASE_URL,
    )
    readiness_check = Mock(return_value=True)
    create_database_readiness_check = Mock(
        return_value=readiness_check
    )
    application = Mock()
    create_app = Mock(return_value=application)
    uvicorn_run = Mock()

    monkeypatch.setattr(
        "extensible_ai_workspace.runtime."
        "create_database_readiness_check",
        create_database_readiness_check,
    )
    monkeypatch.setattr(
        "extensible_ai_workspace.runtime.create_app",
        create_app,
    )
    monkeypatch.setattr(
        "extensible_ai_workspace.runtime.uvicorn.run",
        uvicorn_run,
    )

    run_web(settings)

    create_database_readiness_check.assert_called_once_with(
        TEST_DATABASE_URL
    )
    create_app.assert_called_once_with(
        readiness_check=readiness_check
    )
    uvicorn_run.assert_called_once_with(
        application,
        host="0.0.0.0",
        port=8000,
    )


def test_run_worker_starts_when_database_is_available(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        runtime_role=RuntimeRole.WORKER,
        database_url=TEST_DATABASE_URL,
    )
    check_database_connection = Mock(return_value=True)
    worker_event = Mock()
    event_factory = Mock(return_value=worker_event)

    monkeypatch.setattr(
        "extensible_ai_workspace.runtime.check_database_connection",
        check_database_connection,
    )
    monkeypatch.setattr(
        "extensible_ai_workspace.runtime.Event",
        event_factory,
    )

    from extensible_ai_workspace.runtime import run_worker

    run_worker(settings)

    captured = capsys.readouterr()

    check_database_connection.assert_called_once_with(
        TEST_DATABASE_URL
    )
    event_factory.assert_called_once_with()
    worker_event.wait.assert_called_once_with()
    assert captured.out == (
        "Extensible AI Workspace worker runtime is ready.\n"
    )
    assert captured.err == ""


def test_run_worker_exits_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        runtime_role=RuntimeRole.WORKER,
        database_url=TEST_DATABASE_URL,
    )
    check_database_connection = Mock(return_value=False)

    monkeypatch.setattr(
        "extensible_ai_workspace.runtime.check_database_connection",
        check_database_connection,
    )

    from extensible_ai_workspace.runtime import run_worker

    with pytest.raises(SystemExit) as raised:
        run_worker(settings)

    captured = capsys.readouterr()

    check_database_connection.assert_called_once_with(
        TEST_DATABASE_URL
    )
    assert raised.value.code == 1
    assert captured.out == ""
    assert captured.err == (
        "Worker runtime is not ready. "
        "The configured PostgreSQL database is unavailable.\n"
    )
