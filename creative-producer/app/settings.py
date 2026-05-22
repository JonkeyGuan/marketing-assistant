from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8086
    AGENT_ENDPOINT: str = ""
    MODEL_ENDPOINT: str = ""
    MODEL_NAME: str = "qwen25-coder-32b-fp8"
    MODEL_API_KEY: str = ""
    EVENT_HUB_URL: str = "http://localhost:8080"
    IMAGEGEN_MCP_URL: str = "http://localhost:8083"

    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
