from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str
    bot_token: str
    bot_secret: str
    host: str = "0.0.0.0"
    port: int = 8000
    # Настройки для PostgreSQL (для docker-compose)
    postgres_user: str = "your_postgres_user"
    postgres_password: str = "your_postgres_password"
    postgres_db: str = "your_database_name"
    # Домены для CORS и Mini App
    frontend_domain: str = "https://your-frontend-domain.com"  # Домен фронтенда (Mini App)
    api_domain: str = ""  # Домен API (опционально, для CORS)
    cors_origins: str = ""  # Разрешенные домены для CORS (через запятую, если пусто - используется frontend_domain и api_domain)
    instruction_pdf_url: str = ""  # URL для PDF инструкции (опционально)

    @property
    def get_cors_origins(self) -> List[str]:
        """Возвращает список разрешенных доменов для CORS."""
        if self.cors_origins:
            # Если указаны вручную, используем их
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        else:
            # Иначе используем frontend_domain и api_domain
            origins = [self.frontend_domain]
            if self.api_domain and self.api_domain != self.frontend_domain:
                origins.append(self.api_domain)
            # Добавляем варианты с www
            if self.frontend_domain.startswith("https://"):
                domain_without_protocol = self.frontend_domain.replace("https://", "")
                if not domain_without_protocol.startswith("www."):
                    origins.append(f"https://www.{domain_without_protocol}")
            return origins

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

