from unittest.mock import Mock

import pytest

from extensible_ai_workspace import main
from extensible_ai_workspace.config import RuntimeRole


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
    monkeypatch.setenv("AIW_RUNTIME_ROLE", configured_value)
    run_runtime = Mock()

    monkeypatch.setattr(
        "extensible_ai_workspace.run_runtime",
        run_runtime,
    )

    main()

    run_runtime.assert_called_once_with(expected_role)


def test_main_exits_safely_when_runtime_role_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("AIW_RUNTIME_ROLE", raising=False)

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
    monkeypatch.setenv("AIW_RUNTIME_ROLE", "api")

    with pytest.raises(SystemExit) as raised:
        main()

    captured = capsys.readouterr()

    assert raised.value.code == 2
    assert captured.out == ""
    assert captured.err == (
        "Application configuration is invalid. "
        "Check the required AIW_ environment variables.\n"
    )
