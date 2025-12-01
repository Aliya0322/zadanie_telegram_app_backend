from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import settings
from models import Homework, Group
from datetime import datetime
import pytz
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Глобальный экземпляр бота (будет установлен при запуске)
_bot_instance: Optional[Bot] = None


def get_bot_instance() -> Bot:
    """Получает экземпляр бота. Создает новый, если еще не создан."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Bot(token=settings.bot_token)
    return _bot_instance


def set_bot_instance(bot: Bot):
    """Устанавливает экземпляр бота (используется в bot_runner)."""
    global _bot_instance
    _bot_instance = bot


# Для обратной совместимости
bot = get_bot_instance()


async def send_homework_reminder(student_tg_id: int, homework: Homework, group: Group, user_timezone: str = "UTC"):
    """
    Отправляет напоминание ученику о домашнем задании.
    Учитывает часовой пояс пользователя для отображения времени.
    """
    try:
        bot = get_bot_instance()
        
        # Получаем часовой пояс пользователя
        try:
            user_tz = pytz.timezone(user_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.timezone("UTC")
        
        # Конвертируем дедлайн в часовой пояс пользователя
        deadline_local = homework.deadline.astimezone(user_tz)
        deadline_str = deadline_local.strftime("%Y-%m-%d %H:%M")
        
        message = (
            f"📚 Напоминание о домашнем задании\n\n"
            f"Группа: {group.name}\n"
            f"Задание: {homework.description}\n"
            f"Дедлайн: {deadline_str}\n"
            f"⏰ Осталось менее часа!"
        )
        
        await bot.send_message(chat_id=student_tg_id, text=message)
    except Exception as e:
        print(f"Error sending reminder to {student_tg_id}: {e}")


async def send_class_reminder(student_tg_id: int, group: Group, schedule_item, user_timezone: str = "UTC"):
    """
    Отправляет напоминание ученику о предстоящем занятии с ссылкой.
    """
    try:
        bot = get_bot_instance()
        
        # Формируем сообщение
        message = "Напоминание: Урок через 1 час!\n\n"
        
        if schedule_item.meeting_link:
            message += f"Ссылка на подключение:\n{schedule_item.meeting_link}\n\n"
        
        message += "Проверь, готова ли домашка, и до встречи на занятии! 👋"
        
        # Создаем кнопку "Открыть расписание"
        web_app_url = settings.frontend_domain
        keyboard = None
        
        if web_app_url and web_app_url != "https://your-frontend-domain.com":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Открыть расписание",
                    web_app=WebAppInfo(url=web_app_url)
                )]
            ])
        
        if keyboard:
            await bot.send_message(chat_id=student_tg_id, text=message, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=student_tg_id, text=message)
            
    except Exception as e:
        logger.error(f"Error sending class reminder to {student_tg_id}: {e}")


async def send_new_homework_notification(student_tg_id: int, homework: Homework, group: Group):
    """
    Отправляет уведомление ученику о новом домашнем задании.
    """
    try:
        bot = get_bot_instance()
        
        message = (
            "🔔 Новое домашнее задание!\n\n"
            "Не затягивай!👇"
        )
        
        # Создаем кнопку "Посмотреть задание"
        web_app_url = settings.frontend_domain
        keyboard = None
        
        if web_app_url and web_app_url != "https://your-frontend-domain.com":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Посмотреть задание",
                    web_app=WebAppInfo(url=web_app_url)
                )]
            ])
        
        if keyboard:
            await bot.send_message(chat_id=student_tg_id, text=message, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=student_tg_id, text=message)
            
    except Exception as e:
        logger.error(f"Error sending new homework notification to {student_tg_id}: {e}")


async def close_bot():
    """Закрывает сессию бота."""
    global _bot_instance
    if _bot_instance:
        await _bot_instance.session.close()
        _bot_instance = None

