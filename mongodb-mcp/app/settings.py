from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8082
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "casino_crm"
    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    ALLOW_JWT_FALLBACK: bool = False
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
