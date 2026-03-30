"""
Configuration settings for the K8s Agent service.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """K8s Agent settings loaded from environment variables."""

    # Cluster
    CLUSTER_DOMAIN: str = "apps.your-cluster.example.com"
    DEV_NAMESPACE: str = "0-marketing-assistant-demo-dev"
    PROD_NAMESPACE: str = "0-marketing-assistant-demo-prod"

    # Server settings
    SERVICE_PORT: int = 8004

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
