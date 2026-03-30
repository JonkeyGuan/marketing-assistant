"""
Configuration settings for the Macau Casino Marketing Assistant.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # A2A Agent Endpoints (in-cluster service URLs for OpenShift)
    CODER_A2A_URL: str = "http://coder-agent.0-marketing-assistant-demo.svc.cluster.local:8001"
    CUSTOMER_A2A_URL: str = "http://customer-agent.0-marketing-assistant-demo.svc.cluster.local:8002"
    MARKETING_A2A_URL: str = "http://marketing-agent.0-marketing-assistant-demo.svc.cluster.local:8003"
    K8S_A2A_URL: str = "http://k8s-agent.0-marketing-assistant-demo.svc.cluster.local:8004"
    
    # Email settings
    EMAIL_MODE: str = "simulate"  # "simulate" or "send"
    RESEND_API_KEY: Optional[str] = None
    
    # Localization
    SUPPORTED_LANGUAGES: str = "en,zh-CN"
    DEFAULT_LANGUAGE: str = "en"
    
    # Application settings
    SERVICE_PORT: int = 8501
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
