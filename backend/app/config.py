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
    max_photos: int = 4

    # SQLite file holding cached analyses and saved estimates.
    database_path: str = str(ENV_FILE.parent / "crashtimate.db")
    # Photos, analyses and saved estimates are deleted after this many days.
    retention_days: int = 30

    # Photo analyses one visitor may request per hour, and saved estimates per hour. 0 = no limit.
    rate_limit_per_hour: int = 30
    share_rate_limit_per_hour: int = 60
    # Paid analyses allowed per day across all visitors, to cap spending. 0 = no limit.
    daily_analysis_limit: int = 200
    # Number of reverse proxies in front of the app (1 on Render or Fly.io, 0 locally).
    proxy_hops: int = 0

    vpic_url: str = VPIC_DECODE_URL
    vin_lookup_timeout_seconds: float = 10

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
