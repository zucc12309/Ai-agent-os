from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agent Gateway"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://agent_gateway:agent_gateway@localhost:5432/agent_gateway"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    api_key_pepper: str = "change-me-in-production"
    session_signing_secret: str = "change-me-in-production-session-secret"
    session_cookie_name: str = "agent_gateway_session"
    session_max_age_seconds: int = 60 * 60 * 8
    internal_api_base_url: str | None = None
    frontend_url: str = "http://localhost:3000"
    mcp_mount_path: str = "/mcp"
    demo_operator_api_key: str | None = None

    rate_limit_requests_per_minute: int = 60
    rate_limit_placeholder_enabled: bool = True
    demo_seed_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return list(value)  # type: ignore[arg-type]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
