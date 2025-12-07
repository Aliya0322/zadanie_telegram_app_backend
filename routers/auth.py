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


class LoginRequest(BaseModel):
    """Модель для запроса логина (initData передается в заголовке)"""
    role: Optional[UserRole] = None  # Опциональная роль (teacher/student)
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None
    timezone: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


class UpdateRoleRequest(BaseModel):
    """Модель для обновления роли пользователя."""
    role: UserRole
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None
    timezone: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


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
    
    При создании нового пользователя можно передать:
    - role (teacher/student) - для установки роли
    - Данные анкеты (firstName, lastName, patronymic, birthdate, timezone) в теле запроса.
    
    Если пользователь уже существует, профиль обновляется переданными данными (если они указаны).
    Для полного обновления профиля используйте PUT /api/v1/auth/profile
    """
    # Проверяем initData
    telegram_data = verify_telegram_init_data(x_telegram_init_data)
    if not telegram_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Telegram init data"
        )
    
    user_id = telegram_data['user_id']
    
    # Ищем пользователя в БД
    user = db.query(User).filter(User.tg_id == user_id).first()
    is_new_user = False
    
    # Если пользователя нет, создаем его
    if not user:
        try:
            # Определяем роль (если передана, иначе student по умолчанию)
            role_value = login_data.role if login_data and login_data.role else UserRole.STUDENT
            
            # Определяем часовой пояс
            timezone_value = "UTC"
            if login_data and login_data.timezone:
                timezone_value = login_data.timezone
            
            user = User(
                tg_id=user_id,
                role=role_value,
                timezone=timezone_value,
                is_active=True
            )
            
            # Сохраняем данные анкеты, если они переданы
            if login_data:
                if login_data.firstName:
                    user.first_name = login_data.firstName
                if login_data.lastName:
                    user.last_name = login_data.lastName
                if login_data.patronymic:
                    user.patronymic = login_data.patronymic
                if login_data.birthdate:
                    user.birthdate = login_data.birthdate
                if login_data.timezone:
                    user.timezone = login_data.timezone
            
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new_user = True
            logger.info(f"New user registered with tg_id: {user_id}, role: {role_value.value}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
    else:
        # Если пользователь уже существует, обновляем его профиль, если переданы данные
        if login_data:
            updated = False
            if login_data.firstName:
                user.first_name = login_data.firstName
                updated = True
            if login_data.lastName:
                user.last_name = login_data.lastName
                updated = True
            if login_data.patronymic is not None:
                user.patronymic = login_data.patronymic
                updated = True
            if login_data.birthdate is not None:
                user.birthdate = login_data.birthdate
                updated = True
            if login_data.timezone:
                # Валидируем timezone перед сохранением
                try:
                    import pytz
                    pytz.timezone(login_data.timezone)
                    user.timezone = login_data.timezone
                    updated = True
                    logger.info(f"User {user.tg_id} updated timezone to {login_data.timezone}")
                except pytz.exceptions.UnknownTimeZoneError:
                    logger.warning(f"Invalid timezone '{login_data.timezone}' provided by user {user.tg_id}, keeping current timezone")
            
            if updated:
                db.commit()
                db.refresh(user)
                logger.info(f"User {user.tg_id} profile updated via login")
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return LoginResponse(
        user=UserResponse.model_validate(user),
        isNewUser=is_new_user,
        message="Login successful" if not is_new_user else "Registration successful"
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе."""
    return UserResponse.model_validate(current_user)


@router.get("/users/by-telegram/{tg_id}", response_model=UserResponse)
async def get_user_by_telegram_id(
    tg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить пользователя по Telegram ID.
    
    Доступно для аутентифицированных пользователей.
    Полезно для получения данных студентов, когда известен их Telegram ID (например, из списка группы).
    """
    user = db.query(User).filter(User.tg_id == tg_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить профиль пользователя.
    Позволяет обновить имя, фамилию, отчество, дату рождения и часовой пояс.
    
    Все поля обязательны. Для удаления дня рождения передайте birthdate: null.
    
    Часовой пояс должен быть указан вручную пользователем (например, "Europe/Moscow").
    Это необходимо для корректной работы уведомлений, так как автоматическое определение
    может быть неточным при использовании VPN.
    """
    current_user.first_name = profile_data.firstName
    current_user.last_name = profile_data.lastName
    current_user.patronymic = profile_data.patronymic
    # Явно устанавливаем birthdate (даже если None, чтобы можно было удалить)
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
    logger.info(f"User {current_user.tg_id} profile updated")
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_profile_me(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить профиль пользователя (алиас для /profile).
    Позволяет обновить имя, фамилию, отчество, дату рождения и часовой пояс.
    """
    current_user.first_name = profile_data.firstName
    current_user.last_name = profile_data.lastName
    current_user.patronymic = profile_data.patronymic
    # Явно устанавливаем birthdate (даже если None, чтобы можно было удалить)
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
    logger.info(f"User {current_user.tg_id} profile updated via /me endpoint")
    return UserResponse.model_validate(current_user)


@router.post("/update-role", response_model=UserResponse)
async def update_role(
    role_data: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить роль пользователя и опционально данные профиля.
    
    Используется для смены роли с student на teacher или наоборот.
    При смене роли можно также обновить данные профиля (имя, фамилия, отчество, дата рождения, часовой пояс).
    
    Важно: при смене роли на teacher, пользователь должен заполнить обязательные поля (firstName, lastName).
    """
    # Обновляем роль
    current_user.role = role_data.role
    
    # Обновляем данные профиля, если они переданы
    if role_data.firstName:
        current_user.first_name = role_data.firstName
    if role_data.lastName:
        current_user.last_name = role_data.lastName
    if role_data.patronymic is not None:
        current_user.patronymic = role_data.patronymic
    if role_data.birthdate is not None:
        current_user.birthdate = role_data.birthdate
    if role_data.timezone:
        # Валидируем timezone перед сохранением
        try:
            import pytz
            pytz.timezone(role_data.timezone)
            current_user.timezone = role_data.timezone
            logger.info(f"User {current_user.tg_id} updated timezone to {role_data.timezone}")
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Invalid timezone '{role_data.timezone}' provided by user {current_user.tg_id}, keeping current timezone")
    
    try:
        db.commit()
        db.refresh(current_user)
        logger.info(f"User {current_user.tg_id} role updated to {role_data.role.value}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )
    
    return UserResponse.model_validate(current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Удалить текущего пользователя из БД.
    Внимание: это удалит все связанные данные (группы, домашние задания и т.д.)
    в соответствии с настройками каскадного удаления в БД.
    """
    try:
        db.delete(current_user)
        db.commit()
        logger.info(f"User {current_user.tg_id} deleted from database")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user {current_user.tg_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user account"
        )

