from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8088
    AGENT_ENDPOINT: str = ""
    CREATIVE_PRODUCER_URL: str = "http://localhost:8086"
    CUSTOMER_ANALYST_URL: str = "http://localhost:8084"
    DELIVERY_MANAGER_URL: str = "http://localhost:8087"
    POLICY_GUARDIAN_URL: str = "http://localhost:8085"
    EVENT_HUB_URL: str = "http://localhost:8080"
    CLUSTER_DOMAIN: str = "localhost"
    DEV_NAMESPACE: str = "marketing-dev"
    PROD_NAMESPACE: str = "marketing-prod"

    CAMPAIGN_STORAGE_PATH: str = "/tmp/campaigns"
    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
