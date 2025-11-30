from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import groups, homework, user, auth, schedule
from scheduler import start_scheduler, shutdown_scheduler
from bot_notifier import close_bot
from config import settings
import atexit
import logging

logger = logging.getLogger(__name__)

# Примечание: Таблицы создаются через Alembic миграции
# Для разработки можно раскомментировать следующую строку:
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Telegram Mini App Backend", version="1.0.0")

# CORS middleware для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins,  # Разрешенные домены из переменных окружения
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(homework.router)
app.include_router(user.router)
app.include_router(schedule.router)


@app.on_event("startup")
async def startup_event():
    """Запускает планировщик при старте приложения."""
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """Останавливает планировщик и закрывает сессию бота при выключении."""
    shutdown_scheduler()
    await close_bot()


@app.get("/")
async def root():
    return {"message": "Telegram Mini App Backend API"}


@app.get("/health")
async def health():
    return {"status": "ok"}

