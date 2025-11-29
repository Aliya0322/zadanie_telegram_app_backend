from aiogram import Bot
from config import settings
from models import Homework, Group
from datetime import datetime
import pytz
from typing import Optional

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
        
        # Получаем часовой пояс пользователя
        try:
            user_tz = pytz.timezone(user_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.timezone("UTC")
        
        # Формируем время начала в часовом поясе пользователя
        # schedule_item.time_at хранится как time (без даты), нужно объединить с текущей датой
        now = datetime.now(pytz.utc)
        class_time = datetime.combine(now.date(), schedule_item.time_at)
        # Приводим к UTC для корректной конвертации (предполагаем что в БД время в UTC или локальное сервера, 
        # но лучше хранить UTC. Здесь для простоты считаем, что time_at это локальное время группы/сервера, 
        # но для корректности лучше хранить с tz. Упростим: просто покажем время как есть)
        
        time_str = schedule_item.time_at.strftime("%H:%M")
        
        message = (
            f"🔔 Напоминание о занятии\n\n"
            f"Группа: {group.name}\n"
            f"Время: {time_str}\n"
        )
        
        if schedule_item.meeting_link:
            message += f"\n🔗 Ссылка для подключения:\n{schedule_item.meeting_link}"
        
        message += "\n\n⏰ До начала 1 час!"
        
        await bot.send_message(chat_id=student_tg_id, text=message)
    except Exception as e:
        print(f"Error sending class reminder to {student_tg_id}: {e}")


async def close_bot():
    """Закрывает сессию бота."""
    global _bot_instance
    if _bot_instance:
        await _bot_instance.session.close()
        _bot_instance = None

