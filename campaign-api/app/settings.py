from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8089
    CAMPAIGN_DIRECTOR_URL: str = "http://localhost:8088"
    POLICY_GUARDIAN_URL: str = "http://localhost:8085"
    EVENT_HUB_URL: str = "http://localhost:8080"
    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    HAP_DETECTOR_URL: str = ""
    PROMPT_INJECTION_URL: str = ""
    ORCHESTRATOR_URL: str = ""
    ASSET_STORAGE_PATH: str = "/tmp/campaign-assets"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
