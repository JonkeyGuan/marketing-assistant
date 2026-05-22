from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8084
    AGENT_ENDPOINT: str = ""
    MONGODB_MCP_URL: str = "http://localhost:8082"
    EVENT_HUB_URL: str = "http://localhost:8080"
    MODEL_ENDPOINT: str = ""
    MODEL_NAME: str = "qwen3-32b-fp8-dynamic"
    MODEL_API_KEY: str = ""
    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
