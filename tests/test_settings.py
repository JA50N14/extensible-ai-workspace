import pytest
from pydantic import ValidationError

from extensible_ai_workspace.config import (
    AuthenticationMode,
    DatabaseSettings,
    RuntimeRole,
    Settings,
)

TEST_DATABASE_URL = (
    "postgresql://app:development@localhost:5432/"
    "extensible_ai_workspace"
)
TEST_PUBLIC_ORIGIN = "http://127.0.0.1:8000"


def configure_valid_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    runtime_role: str = "web",
) -> None:
    monkeypatch.setenv("AIW_RUNTIME_ROLE", runtime_role)
    monkeypatch.setenv("AIW_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv(
        "AIW_AUTHENTICATION_MODE",
        "local_trusted",
    )
    monkeypatch.setenv(
        "AIW_PUBLIC_ORIGIN",
        TEST_PUBLIC_ORIGIN,
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
def test_settings_accepts_supported_runtime_roles(
    monkeypatch: pytest.MonkeyPatch,
    configured_value: str,
    expected_role: RuntimeRole,
) -> None:
    configure_valid_settings(
        monkeypatch,
        runtime_role=configured_value,
    )

    settings = Settings()

    assert settings.runtime_role is expected_role
    assert settings.database_url == TEST_DATABASE_URL
    assert (
        settings.authentication_mode
        is AuthenticationMode.LOCAL_TRUSTED
    )
    assert str(settings.public_origin) == (
        "http://127.0.0.1:8000/"
    )


def test_settings_rejects_missing_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.delenv("AIW_RUNTIME_ROLE")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unsupported_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.setenv("AIW_RUNTIME_ROLE", "api")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.delenv("AIW_DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_missing_authentication_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.delenv("AIW_AUTHENTICATION_MODE")

    with pytest.raises(ValidationError):
        Settings()


def test_trusted_local_mode_rejects_non_loopback_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.setenv(
        "AIW_PUBLIC_ORIGIN",
        "http://192.168.1.10:8000",
    )

    with pytest.raises(
        ValidationError,
        match="loopback public origin",
    ):
        Settings()


@pytest.mark.parametrize(
    "missing_environment_variable",
    [
        "AIW_LOCAL_IDENTITY_ISSUER",
        "AIW_LOCAL_IDENTITY_SUBJECT",
        "AIW_LOCAL_IDENTITY_DISPLAY_NAME",
    ],
)
def test_trusted_local_mode_requires_identity_configuration(
    monkeypatch: pytest.MonkeyPatch,
    missing_environment_variable: str,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.delenv(missing_environment_variable)

    with pytest.raises(
        ValidationError,
        match="explicit local identity configuration",
    ):
        Settings()


def test_trusted_local_identity_values_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.setenv(
        "AIW_LOCAL_IDENTITY_DISPLAY_NAME",
        "  Local User  ",
    )

    settings = Settings()

    assert settings.local_identity_display_name == "Local User"


def test_trusted_local_identity_values_cannot_be_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_valid_settings(monkeypatch)
    monkeypatch.setenv(
        "AIW_LOCAL_IDENTITY_SUBJECT",
        "   ",
    )

    with pytest.raises(
        ValidationError,
        match="cannot be blank",
    ):
        Settings()


def test_database_settings_require_only_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIW_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.delenv("AIW_RUNTIME_ROLE", raising=False)
    monkeypatch.delenv(
        "AIW_AUTHENTICATION_MODE",
        raising=False,
    )
    monkeypatch.delenv("AIW_PUBLIC_ORIGIN", raising=False)

    settings = DatabaseSettings()

    assert settings.database_url == TEST_DATABASE_URL
