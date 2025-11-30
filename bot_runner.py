"""
Отдельный процесс для запуска Telegram бота.
Обрабатывает входящие команды через Polling.
"""
import asyncio
import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from config import settings
from bot_handler import create_dispatcher, set_bot_commands
# Импорт set_bot_instance будет сделан позже, чтобы избежать циклических зависимостей

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота."""
    logger.info("Starting Telegram Bot...")
    
    # Создаем бота
    bot = Bot(
        token=settings.bot_token,
        parse_mode=ParseMode.HTML
    )
    
    # Устанавливаем команды бота
    try:
        await set_bot_commands(bot)
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.error(f"Error setting bot commands: {e}")
    
    # Создаем диспетчер
    dp = create_dispatcher()
    
    # Регистрируем экземпляр бота для использования в bot_notifier
    # Это позволяет отправлять уведомления из других частей приложения
    from bot_notifier import set_bot_instance
    set_bot_instance(bot)
    
    try:
        # Запускаем polling
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"Error in polling: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

