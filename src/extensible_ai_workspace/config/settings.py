"""Validated application settings."""

from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeRole(StrEnum):
    """Supported application runtime roles."""

    WEB = "web"
    WORKER = "worker"


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
