from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8083
    MODEL_ENDPOINT: str = ""
    MODEL_NAME: str = "flux2-klein-4b"
    MODEL_API_KEY: str = ""
    CONFIG_SERVICE_URL: str = "http://localhost:8081"
    IMAGE_STORAGE_PATH: str = "/tmp/images"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
