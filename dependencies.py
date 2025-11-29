from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from telegram_auth import verify_telegram_init_data
import logging

logger = logging.getLogger(__name__)


async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db)
) -> User:
    """
    Зависимость FastAPI для получения текущего пользователя из Telegram initData.
    
    Безопасность:
    - Проверяет криптографическую подпись initData
    - Проверяет срок действия initData (не старше 24 часов)
    - Извлекает user_id только после успешной проверки
    
    Args:
        x_telegram_init_data: Заголовок X-Telegram-Init-Data с данными от Telegram
        db: Сессия базы данных
        
    Returns:
        User: Объект пользователя из базы данных
        
    Raises:
        HTTPException 401: Если initData невалиден или проверка не прошла
        HTTPException 403: Если пользователь неактивен
    """
    # Проверяем initData
    telegram_data = verify_telegram_init_data(x_telegram_init_data)
    if not telegram_data:
        logger.warning("Failed to verify Telegram init data")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Telegram init data. Please refresh the page."
        )
    
    user_id = telegram_data['user_id']
    user_data = telegram_data.get('user_data', {})
    
    # Ищем пользователя в БД
    user = db.query(User).filter(User.tg_id == user_id).first()
    
    # Если пользователя нет, создаем его с ролью student по умолчанию
    # Примечание: здесь timezone будет UTC, так как нет доступа к данным запроса
    # Для правильного определения timezone используйте эндпоинт /api/v1/auth/login
    if not user:
        try:
            user = User(
                tg_id=user_id,
                role=UserRole.STUDENT,
                timezone="UTC",  # По умолчанию UTC, можно обновить через /profile
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user with tg_id: {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
    
    if not user.is_active:
        logger.warning(f"Inactive user attempted to access: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def get_teacher_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Зависимость для проверки, что пользователь является учителем."""
    if current_user.role.value != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can perform this action")
    return current_user


async def get_student_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Зависимость для проверки, что пользователь является учеником."""
    if current_user.role.value != "student":
        raise HTTPException(status_code=403, detail="Only students can perform this action")
    return current_user

