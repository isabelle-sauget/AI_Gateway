"""Application settings loaded from environment variables and .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = ROOT_DIR / ".env"

class Settings(BaseSettings):
    """Configuration shared by the application services."""

    APP_NAME: str = "GDPR AI Gateway API"
    REDIS_URL: str = "redis://localhost:6379/0"
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_API_KEY: str
    
    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), extra="ignore")


settings = Settings() # type: ignore

