from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from database import engine, Base
from routers import groups, homework, user, auth, schedule
from scheduler import start_scheduler, shutdown_scheduler
from bot_notifier import close_bot
from config import settings
import atexit
import logging
import traceback

logger = logging.getLogger(__name__)

# Примечание: Таблицы создаются через Alembic миграции
# Для разработки можно раскомментировать следующую строку:
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Telegram Mini App Backend", version="1.0.0")

# CORS middleware для работы с фронтендом
# ВАЖНО: CORS middleware должен быть добавлен ПЕРЕД другими middleware
cors_origins = settings.get_cors_origins
logger.info(f"CORS allowed origins: {cors_origins}")


# Middleware для логирования CORS запросов
class CORSLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            is_allowed = origin in cors_origins
            logger.info(f"CORS request from origin: {origin}, allowed: {is_allowed}")
        
        response = await call_next(request)
        return response


# Добавляем middleware для логирования (перед CORS middleware)
app.add_middleware(CORSLoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Разрешенные домены из переменных окружения
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Вспомогательная функция для проверки и добавления CORS headers
def add_cors_headers(response: JSONResponse, origin: str = None) -> JSONResponse:
    """Добавляет CORS headers к ответу, если origin разрешен."""
    if not origin:
        return response
    
    # Проверяем, разрешен ли этот origin
    is_allowed = origin in cors_origins
    
    if is_allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    else:
        logger.warning(f"CORS: Origin '{origin}' is not allowed. Allowed origins: {cors_origins}")
    
    return response


# Глобальный обработчик исключений для обеспечения CORS headers при ошибках
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик исключений, который гарантирует наличие CORS headers
    даже при необработанных ошибках.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Получаем origin из запроса
    origin = request.headers.get("origin")
    
    # Формируем ответ с ошибкой
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.host == "0.0.0.0" else "An error occurred"
        }
    )
    
    # Добавляем CORS headers
    return add_cors_headers(response, origin)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Обработчик HTTP исключений с CORS headers."""
    origin = request.headers.get("origin")
    
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    
    return add_cors_headers(response, origin)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации с CORS headers."""
    origin = request.headers.get("origin")
    
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )
    
    return add_cors_headers(response, origin)

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


@app.get("/cors-test")
async def cors_test(request: Request):
    """Тестовый endpoint для проверки CORS настроек."""
    origin = request.headers.get("origin")
    return {
        "message": "CORS test endpoint",
        "request_origin": origin,
        "allowed_origins": cors_origins,
        "origin_allowed": origin in cors_origins if origin else False
    }

