from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8081
    VERTICAL_CONFIG: str = "hotel-casino"
    VERTICAL_CONFIG_DIR: str = "app/verticals"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
