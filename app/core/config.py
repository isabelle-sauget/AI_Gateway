"""Application settings loaded from environment variables and .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by the application services."""

    app_name: str = "GDPR AI Gateway API"
    redis_url: str = "redis://localhost:6379/0"
    gemini_model: str = "gemini-3.6-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
