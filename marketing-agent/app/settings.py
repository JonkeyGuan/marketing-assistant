"""
Configuration settings for the Marketing Agent service.
"""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Marketing Agent settings loaded from environment variables."""

    # LLM endpoint (OpenAI-compatible)
    MODEL_ENDPOINT: str = "https://your-model-endpoint/v1"
    MODEL_NAME: str = "your-model-name"
    MODEL_TOKEN: Optional[str] = None

    # Server settings
    SERVICE_PORT: int = 8003

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
