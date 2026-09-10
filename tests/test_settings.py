import pytest
from pydantic import ValidationError

from extensible_ai_workspace.config import RuntimeRole, Settings

TEST_DATABASE_URL = (
    "postgresql://app:development@localhost:5432/"
    "extensible_ai_workspace"
)


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
    monkeypatch.setenv("AIW_DATABASE_URL", TEST_DATABASE_URL)

    settings = Settings()

    assert settings.runtime_role is expected_role
    assert settings.database_url == TEST_DATABASE_URL


def test_settings_rejects_missing_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AIW_RUNTIME_ROLE", raising=False)
    monkeypatch.setenv("AIW_DATABASE_URL", TEST_DATABASE_URL)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unsupported_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIW_RUNTIME_ROLE", "api")
    monkeypatch.setenv("AIW_DATABASE_URL", TEST_DATABASE_URL)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIW_RUNTIME_ROLE", "web")
    monkeypatch.delenv("AIW_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()
