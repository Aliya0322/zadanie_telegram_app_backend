"""
Утилиты для работы с ботом и генерации ссылок.
"""
from aiogram import Bot
from config import settings
import logging

logger = logging.getLogger(__name__)

# Кэш для username бота (чтобы не делать запрос каждый раз)
_bot_username_cache: str | None = None


async def get_bot_username(bot: Bot = None) -> str:
    """
    Получает username бота через Bot API.
    Использует кэш для оптимизации.
    """
    global _bot_username_cache
    
    if _bot_username_cache:
        return _bot_username_cache
    
    try:
        if bot is None:
            bot = Bot(token=settings.bot_token)
        
        bot_info = await bot.get_me()
        _bot_username_cache = bot_info.username
        return _bot_username_cache
    except Exception as e:
        logger.error(f"Error getting bot username: {e}")
        # Возвращаем заглушку в случае ошибки
        return "your_bot_username"


def generate_invite_link(invite_code: str, bot_username: str = None) -> str:
    """
    Генерирует ссылку-приглашение для Telegram Deep Linking.
    Формат: t.me/BotUsername?start=group_XYZ1A2B3C
    
    Args:
        invite_code: Уникальный код приглашения группы
        bot_username: Username бота (если не указан, используется кэш или заглушка)
    
    Returns:
        Ссылка-приглашение в формате Telegram Deep Link
    """
    if not bot_username:
        bot_username = _bot_username_cache or "your_bot_username"
    
    return f"https://t.me/{bot_username}?start=group_{invite_code}"

