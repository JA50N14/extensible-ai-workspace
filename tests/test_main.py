from unittest.mock import Mock

import pytest

from extensible_ai_workspace import main
from extensible_ai_workspace.config import RuntimeRole, Settings

TEST_DATABASE_URL = (
    "postgresql://app:development@localhost:5432/"
    "extensible_ai_workspace"
)

def configure_valid_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    runtime_role: str,
) -> None:
    monkeypatch.setenv("AIW_RUNTIME_ROLE", runtime_role)
    monkeypatch.setenv("AIW_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv(
        "AIW_AUTHENTICATION_MODE",
        "local_trusted",
    )
    monkeypatch.setenv(
        "AIW_PUBLIC_ORIGIN",
        "http://127.0.0.1:8000",
    )
    monkeypatch.setenv(
        "AIW_LOCAL_IDENTITY_ISSUER",
        "extensible-ai-workspace-local",
    )
    monkeypatch.setenv(
        "AIW_LOCAL_IDENTITY_SUBJECT",
        "local-user",
    )
    monkeypatch.setenv(
        "AIW_LOCAL_IDENTITY_DISPLAY_NAME",
        "Local User",
    )

@pytest.mark.parametrize(
    ("configured_value", "expected_role"),
    [
        ("web", RuntimeRole.WEB),
        ("worker", RuntimeRole.WORKER),
    ],
)
def test_main_dispatches_configured_runtime(
    monkeypatch: pytest.MonkeyPatch,
    configured_value: str,
    expected_role: RuntimeRole,
) -> None:
    configure_valid_environment(
        monkeypatch,
        runtime_role=configured_value,
    )
    run_runtime = Mock()

    monkeypatch.setattr(
        "extensible_ai_workspace.run_runtime",
        run_runtime,
    )

    main()

    run_runtime.assert_called_once()

    settings = run_runtime.call_args.args[0]

    assert isinstance(settings, Settings)
    assert settings.runtime_role is expected_role
    assert settings.database_url == TEST_DATABASE_URL


def test_main_exits_safely_when_runtime_role_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:

    configure_valid_environment(
        monkeypatch,
        runtime_role="web",
    )
    monkeypatch.delenv("AIW_RUNTIME_ROLE")

    with pytest.raises(SystemExit) as raised:
        main()

    captured = capsys.readouterr()

    assert raised.value.code == 2
    assert captured.out == ""
    assert captured.err == (
        "Application configuration is invalid. "
        "Check the required AIW_ environment variables.\n"
    )


def test_main_exits_safely_when_runtime_role_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_valid_environment(
        monkeypatch,
        runtime_role="api",
    )

    with pytest.raises(SystemExit) as raised:
        main()

    captured = capsys.readouterr()

    assert raised.value.code == 2
    assert captured.out == ""
    assert captured.err == (
        "Application configuration is invalid. "
        "Check the required AIW_ environment variables.\n"
    )
