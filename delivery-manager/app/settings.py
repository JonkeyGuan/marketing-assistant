from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8087
    AGENT_ENDPOINT: str = ""
    MODEL_ENDPOINT: str = ""
    MODEL_NAME: str = "qwen3-32b-fp8-dynamic"
    MODEL_API_KEY: str = ""
    CAMPAIGN_API_URL: str = "http://localhost:8089"
    EVENT_HUB_URL: str = "http://localhost:8080"
    CLUSTER_DOMAIN: str = "localhost"
    DEV_NAMESPACE: str = "marketing-dev"
    PROD_NAMESPACE: str = "marketing-prod"
    APP_NAMESPACE: str = "marketing"
    LANDING_IMAGE: str = "quay.io/rh-ee-dayeo/marketing-assistant:campaign-landing"

    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
