from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str
    bot_token: str
    bot_secret: str
    host: str = "0.0.0.0"
    port: int = 8000
    # Настройки для PostgreSQL (для docker-compose)
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "telegram_app_db"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

