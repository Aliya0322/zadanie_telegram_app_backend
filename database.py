from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Создаем engine с настройками для production
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Проверяет соединения перед использованием
    pool_recycle=3600,   # Переиспользует соединения каждый час
    echo=False           # Установите True для отладки SQL запросов
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base для всех моделей (используется Alembic)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

