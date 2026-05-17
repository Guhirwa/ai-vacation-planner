from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./ai_vacation_planner.db"
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_in: int = 30
    debug: bool = True
    app_name: str = "AI Vacation Planner APIs"
    api_version: str = "1.0.0"

    class Config:
        enc_file = ".env"

settings = Settings()

