from fastapi import APIRouter, Depends, HTTPException, Header, status, Body
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from schemas import UserResponse, LoginResponse, UserUpdate
from dependencies import get_current_user
from telegram_auth import verify_telegram_init_data
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UpdateRoleRequest(BaseModel):
    role: UserRole
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    middle_name: Optional[str] = Field(None, alias="middleName")
    patronymic: Optional[str] = None  # Для совместимости с фронтендом (middleName -> patronymic)
    birth_date: Optional[datetime] = Field(None, alias="birthDate")
    birthdate: Optional[datetime] = None  # Для совместимости с фронтендом
    timezone: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)  # Позволяет использовать как alias, так и имя поля


class LoginRequest(BaseModel):
    """Модель для запроса логина (initData передается в заголовке)"""
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    middle_name: Optional[str] = Field(None, alias="middleName")
    patronymic: Optional[str] = None  # Для совместимости с фронтендом (middleName -> patronymic)
    birth_date: Optional[datetime] = Field(None, alias="birthDate")
    birthdate: Optional[datetime] = None  # Для совместимости с фронтендом
    timezone: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)  # Позволяет использовать как alias, так и имя поля


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: Optional[LoginRequest] = Body(None),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db)
):
    """
    Первичная регистрация/авторизация пользователя.
    
    При первом запуске Mini App фронтенд отправляет initData.
    Бэкенд верифицирует, и если пользователя нет в БД, создает новую запись
    с ролью student (по умолчанию) и возвращает статус.
    
    Можно передать данные анкеты (first_name, last_name, patronymic/middle_name, birthdate, timezone) в теле запроса.
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
    
    # Если пользователя нет, создаем его
    if not user:
        try:
            # Определяем часовой пояс
            timezone_value = "UTC"
            if login_data and login_data.timezone:
                timezone_value = login_data.timezone
            elif login_data is None:
                # Если login_data не передан, используем UTC
                timezone_value = "UTC"
            
            user = User(
                tg_id=user_id,
                role=UserRole.STUDENT,
                timezone=timezone_value,
                is_active=True
            )
            
            # Сохраняем данные анкеты, если они переданы
            if login_data:
                if login_data.first_name:
                    user.first_name = login_data.first_name
                if login_data.last_name:
                    user.last_name = login_data.last_name
                # Поддерживаем оба варианта: patronymic и middle_name
                patronymic_value = login_data.patronymic or login_data.middle_name
                if patronymic_value:
                    user.patronymic = patronymic_value
                # Поддерживаем оба варианта: birthdate и birth_date
                birthdate_value = login_data.birthdate or login_data.birth_date
                if birthdate_value:
                    user.birthdate = birthdate_value
            
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
    else:
        # Если пользователь уже существует, обновляем данные анкеты, если они переданы
        if login_data:
            updated = False
            if login_data.first_name:
                user.first_name = login_data.first_name
                updated = True
            if login_data.last_name:
                user.last_name = login_data.last_name
                updated = True
            # Поддерживаем оба варианта: patronymic и middle_name
            patronymic_value = login_data.patronymic or login_data.middle_name
            if patronymic_value:
                user.patronymic = patronymic_value
                updated = True
            # Поддерживаем оба варианта: birthdate и birth_date
            birthdate_value = login_data.birthdate or login_data.birth_date
            if birthdate_value:
                user.birthdate = birthdate_value
                updated = True
            if login_data.timezone:
                # Валидируем часовой пояс
                try:
                    import pytz
                    pytz.timezone(login_data.timezone)
                    user.timezone = login_data.timezone
                    updated = True
                    logger.info(f"User {user_id} timezone updated to {login_data.timezone}")
                except pytz.exceptions.UnknownTimeZoneError:
                    logger.warning(f"Invalid timezone '{login_data.timezone}' provided, keeping existing timezone")
            
            if updated:
                db.commit()
                db.refresh(user)
                logger.info(f"User {user_id} profile updated during login")
    
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
    """
    Обновить роль пользователя и данные анкеты (для регистрации как учитель/ученик).
    
    Принимает роль и опционально данные анкеты (first_name, last_name, patronymic/middle_name, birthdate, timezone).
    """
    # Обновляем роль
    current_user.role = role_data.role
    
    # Обновляем данные анкеты, если они переданы
    if role_data.first_name:
        current_user.first_name = role_data.first_name
    if role_data.last_name:
        current_user.last_name = role_data.last_name
    # Поддерживаем оба варианта: patronymic и middle_name
    patronymic_value = role_data.patronymic or role_data.middle_name
    if patronymic_value:
        current_user.patronymic = patronymic_value
    # Поддерживаем оба варианта: birthdate и birth_date
    birthdate_value = role_data.birthdate or role_data.birth_date
    if birthdate_value:
        current_user.birthdate = birthdate_value
    if role_data.timezone:
        # Валидируем часовой пояс
        try:
            import pytz
            pytz.timezone(role_data.timezone)
            current_user.timezone = role_data.timezone
            logger.info(f"User {current_user.tg_id} timezone updated to {role_data.timezone}")
        except pytz.exceptions.UnknownTimeZoneError:
            logger.error(f"Invalid timezone '{role_data.timezone}' provided by user {current_user.tg_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timezone: {role_data.timezone}. Please use a valid timezone like 'Europe/Moscow' or 'America/New_York'"
            )
    
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.tg_id} role updated to {role_data.role.value}")
    return {"message": "Role updated successfully", "user": UserResponse.model_validate(current_user)}


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

