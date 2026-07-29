from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration, loaded from environment variables (.env)."""

    database_url: str = "sqlite:///./ai_vacation_planner.db"
    secret_key: str = Field(...)
    anthropic_api_key: str = Field(...)
    algorithm: str = "HS256"
    access_token_expire_in: int = 30
    debug: bool = True
    app_name: str = "AI Vacation Planner APIs"
    api_version: str = "1.0.0"
    llm_max_retries: int = 3
    weather_api_timeout: int = 10  # seconds before the weather API call times out

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

