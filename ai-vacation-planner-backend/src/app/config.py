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
    chroma_persist_path: str = "./chroma_db"
    knowledge_top_k: int = 3

    agent_model: str = "claude-haiku-4-5"
    """The model the LangGraph agent uses for reasoning and tool calls."""

    agent_max_iterations: int = 10
    """Maximum number of tool-call cycles the agent may run before it must stop."""

    whisper_model_size: str = "base"
    # Whisper model size to load locally. Options: tiny, base, small, medium, large.
    # Larger models are more accurate but slower and use more memory.
    # "base" is a good balance for development.

    whisper_device: str = "cpu"
    # Device to run the Whisper model on. Use "cpu" for most machines.
    # Change to "cuda" if a GPU is available.

    whisper_compute_type: str = "int8"
    # Compute type for the Whisper model. "int8" is fastest on CPU.
    # Use "float16" for GPU inference.

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

