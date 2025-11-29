from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from schemas import UserResponse, LoginResponse, UserUpdate
from dependencies import get_current_user
from telegram_auth import verify_telegram_init_data
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UpdateRoleRequest(BaseModel):
    role: UserRole


class LoginRequest(BaseModel):
    """Модель для запроса логина (initData передается в заголовке)"""
    pass


@router.post("/login", response_model=LoginResponse)
async def login(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db)
):
    """
    Первичная регистрация/авторизация пользователя.
    
    При первом запуске Mini App фронтенд отправляет initData.
    Бэкенд верифицирует, и если пользователя нет в БД, создает новую запись
    с ролью student (по умолчанию) и возвращает статус.
    """
    # Проверяем initData
    telegram_data = verify_telegram_init_data(x_telegram_init_data)
    if not telegram_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Telegram init data"
        )
    
    user_id = telegram_data['user_id']
    user_data = telegram_data.get('user_data', {})
    
    # Ищем пользователя в БД
    user = db.query(User).filter(User.tg_id == user_id).first()
    is_new_user = False
    
    # Если пользователя нет, создаем его с ролью student по умолчанию
    # Часовой пояс будет установлен пользователем вручную при заполнении профиля
    if not user:
        try:
            user = User(
                tg_id=user_id,
                role=UserRole.STUDENT,
                timezone="UTC",  # По умолчанию UTC, пользователь установит при заполнении профиля
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new_user = True
            logger.info(f"New user registered with tg_id: {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return LoginResponse(
        user=UserResponse.model_validate(user),
        is_new_user=is_new_user,
        message="Login successful" if not is_new_user else "Registration successful"
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе."""
    return current_user


@router.post("/update-role")
async def update_role(
    role_data: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить роль пользователя (для регистрации как учитель)."""
    current_user.role = role_data.role
    db.commit()
    db.refresh(current_user)
    return {"message": "Role updated successfully", "user": current_user}


@router.post("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить профиль пользователя.
    Позволяет установить имя, фамилию, отчество, дату рождения и часовой пояс.
    
    Часовой пояс должен быть указан вручную пользователем (например, "Europe/Moscow").
    Это необходимо для корректной работы уведомлений, так как автоматическое определение
    может быть неточным при использовании VPN.
    """
    current_user.first_name = profile_data.first_name
    current_user.last_name = profile_data.last_name
    current_user.patronymic = profile_data.patronymic
    
    if profile_data.birthdate:
        current_user.birthdate = profile_data.birthdate
    
    # Валидируем и устанавливаем часовой пояс
    try:
        import pytz
        pytz.timezone(profile_data.timezone)
        current_user.timezone = profile_data.timezone
        logger.info(f"User {current_user.tg_id} updated timezone to {profile_data.timezone}")
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Invalid timezone '{profile_data.timezone}' provided by user {current_user.tg_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid timezone: {profile_data.timezone}. Please use a valid timezone like 'Europe/Moscow' or 'America/New_York'"
        )
        
    db.commit()
    db.refresh(current_user)
    return current_user

