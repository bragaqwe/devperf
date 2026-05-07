from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "DevPerf API"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://devperf:devperf_secret@db:5432/devperf"

    GITHUB_TOKEN: Optional[str] = None
    JIRA_BASE_URL: Optional[str] = None
    JIRA_EMAIL: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    GIGACHAT_AUTH_KEY: Optional[str] = None

    WEIGHT_DELIVERY:      float = 0.35
    WEIGHT_QUALITY:       float = 0.30
    WEIGHT_COLLABORATION: float = 0.20
    WEIGHT_CONSISTENCY:   float = 0.15

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
