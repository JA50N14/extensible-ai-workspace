"""Validated application settings."""

from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeRole(StrEnum):
    """Supported application runtime roles."""

    WEB = "web"
    WORKER = "worker"


class Settings(BaseSettings):
    """Configuration loaded through the application boundary."""

    runtime_role: RuntimeRole
    database_url: str

    model_config = SettingsConfigDict(
        env_prefix="AIW_",
        extra="ignore",
    )

