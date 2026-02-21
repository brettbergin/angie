"""Application configuration via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Angie"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(..., description="JWT signing secret")

    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "angie"
    db_user: str = "angie"
    db_password: str = Field(..., description="MySQL password")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 30

    # LLM — GitHub Models API (preferred) or OpenAI fallback
    github_token: str | None = None
    copilot_model: str = "gpt-4o"
    openai_api_key: str | None = None
    # GitHub Models OpenAI-compatible endpoint
    github_models_api_base: str = "https://models.inference.ai.azure.com"

    # Slack
    slack_bot_token: str | None = None
    slack_app_token: str | None = None
    slack_signing_secret: str | None = None

    # Discord
    discord_bot_token: str | None = None

    # BlueBubbles (iMessage)
    bluebubbles_url: str | None = None
    bluebubbles_password: str | None = None

    # Email (SMTP/IMAP)
    email_smtp_host: str | None = None
    email_smtp_port: int = 587
    email_imap_host: str | None = None
    email_imap_port: int = 993
    email_username: str | None = None
    email_password: str | None = None

    # Google APIs
    google_credentials_file: str | None = None
    google_token_file: str = "token.json"

    # Spotify
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://localhost:8080/callback"

    # Philips Hue
    hue_bridge_ip: str | None = None
    hue_username: str | None = None

    # Home Assistant
    home_assistant_url: str | None = None
    home_assistant_token: str | None = None

    # Ubiquiti / UniFi
    unifi_host: str | None = None
    unifi_username: str | None = None
    unifi_password: str | None = None

    # GitHub
    github_pat: str | None = None

    # Celery
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    @property
    def effective_celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    # Prompts directory
    prompts_dir: str = "prompts"
    user_prompts_dir: str = "prompts/user"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
