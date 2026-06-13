from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./ai_vacation_planner.db"
    secret_key: str = Field(...)
    algorithm: str = "HS256"
    access_token_expire_in: int = 30
    debug: bool = True
    app_name: str = "AI Vacation Planner APIs"
    api_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

