"""Validated application settings."""

from enum import StrEnum
from typing import Self

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeRole(StrEnum):
    """Supported application runtime roles."""

    WEB = "web"
    WORKER = "worker"


class AuthenticationMode(StrEnum):
    """Supported application authentication modes."""

    LOCAL_TRUSTED = "local_trusted"


class DatabaseSettings(BaseSettings):
    """Database configuration shared by application and migration commands."""

    database_url: str

    model_config = SettingsConfigDict(
        env_prefix="AIW_",
        extra="ignore",
    )


class Settings(DatabaseSettings):
    """Configuration required to start an application runtime."""

    runtime_role: RuntimeRole
    authentication_mode: AuthenticationMode
    public_origin: AnyHttpUrl

    local_identity_issuer: str | None = Field(
        default=None,
        max_length=255,
    )
    local_identity_subject: str | None = Field(
        default=None,
        max_length=255,
    )
    local_identity_display_name: str | None = Field(
        default=None,
        max_length=255,
    )

    @field_validator(
        "local_identity_issuer",
        "local_identity_subject",
        "local_identity_display_name",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """Trim configured identity text and reject blank values."""

        if value is None:
            return None

        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError(
                "Configured local identity values cannot be blank."
            )

        return normalized_value

    @model_validator(mode="after")
    def validate_authentication_configuration(self) -> Self:
        """Reject incomplete or remotely exposed trusted-local mode."""

        if self.authentication_mode is AuthenticationMode.LOCAL_TRUSTED:
            if self.public_origin.host not in {
                "127.0.0.1",
                "localhost",
                "::1",
            }:
                raise ValueError(
                    "Trusted-local authentication requires a "
                    "loopback public origin."
                )

            missing_fields = [
                field_name
                for field_name in (
                    "local_identity_issuer",
                    "local_identity_subject",
                    "local_identity_display_name",
                )
                if getattr(self, field_name) is None
            ]

            if missing_fields:
                raise ValueError(
                    "Trusted-local authentication requires explicit "
                    "local identity configuration."
                )

        return self
