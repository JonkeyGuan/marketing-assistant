"""
Configuration settings for the Customer Agent service.
"""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Customer Agent settings loaded from environment variables."""

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "casino_crm"

    # Server settings
    SERVICE_PORT: int = 8002

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
