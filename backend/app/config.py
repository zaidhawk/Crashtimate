from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.vehicles import VPIC_DECODE_URL

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """App settings, read from environment variables prefixed CRASHTIMATE_ or backend/.env."""

    model_config = SettingsConfigDict(
        env_prefix="CRASHTIMATE_",
        env_file=ENV_FILE,
        env_ignore_empty=True,
        extra="ignore",
    )

    detector: Literal["mock", "claude"] = "mock"
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    claude_model: str = "claude-opus-5-5"
    claude_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"

    max_upload_mb: float = 10
    max_image_edge: int = 1568

    vpic_url: str = VPIC_DECODE_URL
    vin_lookup_timeout_seconds: float = 10

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
