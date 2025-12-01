from pydantic_settings import BaseSettings
from pydantic import ValidationError
from typing import List
import sys


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


# Создаем settings с обработкой ошибок
try:
    settings = Settings()
except ValidationError as e:
    missing_fields = []
    for error in e.errors():
        field = error.get('loc', ['unknown'])[0]
        missing_fields.append(field.upper())
    
    error_msg = f"Missing required environment variables: {', '.join(missing_fields)}\n"
    error_msg += "Please set these variables in your .env file or environment.\n"
    error_msg += f"Error details: {e}"
    
    print(error_msg, file=sys.stderr)
    sys.exit(1)
except Exception as e:
    error_msg = f"Failed to load settings: {e}\n"
    error_msg += "Please check your .env file and environment variables."
    print(error_msg, file=sys.stderr)
    sys.exit(1)

