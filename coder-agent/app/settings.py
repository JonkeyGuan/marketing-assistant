"""
Configuration settings for the Coder Agent service.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Coder Agent settings loaded from environment variables."""

    # LLM endpoint (OpenAI-compatible)
    MODEL_ENDPOINT: str = "https://your-model-endpoint/v1"
    MODEL_NAME: str = "your-model-name"
    MODEL_TOKEN: Optional[str] = None

    # Server settings
    SERVICE_PORT: int = 8001

    # Application settings
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
