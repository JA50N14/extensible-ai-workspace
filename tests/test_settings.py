import pytest
from pydantic import ValidationError

from extensible_ai_workspace.config import RuntimeRole, Settings


@pytest.mark.parametrize(
    ("configured_value", "expected_role"),
    [
        ("web", RuntimeRole.WEB),
        ("worker", RuntimeRole.WORKER),
    ],
)
def test_settings_accepts_supported_runtime_roles(
    monkeypatch: pytest.MonkeyPatch,
    configured_value: str,
    expected_role: RuntimeRole,
) -> None:
    monkeypatch.setenv("AIW_RUNTIME_ROLE", configured_value)

    settings = Settings()

    assert settings.runtime_role is expected_role


def test_settings_rejects_missing_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AIW_RUNTIME_ROLE", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unsupported_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIW_RUNTIME_ROLE", "api")

    with pytest.raises(ValidationError):
        Settings()
