"""
Отдельный процесс для запуска Telegram бота.
Обрабатывает входящие команды через Polling.
"""
import asyncio
import logging
import sys
import traceback

# Настройка логирования ДО импорта других модулей
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 50)
logger.info("Bot runner script starting...")
logger.info("=" * 50)

try:
    from aiogram import Bot
    from aiogram.enums import ParseMode
    logger.info("Successfully imported aiogram")
except Exception as e:
    logger.error(f"Failed to import aiogram: {e}", exc_info=True)
    sys.exit(1)

try:
    from config import settings
    logger.info("Successfully imported config")
except Exception as e:
    logger.error(f"Failed to import config: {e}", exc_info=True)
    sys.exit(1)

try:
    from bot_handler import create_dispatcher, set_bot_commands
    logger.info("Successfully imported bot_handler")
except Exception as e:
    logger.error(f"Failed to import bot_handler: {e}", exc_info=True)
    sys.exit(1)


async def main():
    """Основная функция запуска бота."""
    logger.info("Starting Telegram Bot...")
    
    # Проверяем наличие обязательных настроек
    if not settings.bot_token:
        logger.error("BOT_TOKEN is not set in environment variables")
        sys.exit(1)
    
    bot = None
    try:
        # Создаем бота
        bot = Bot(
            token=settings.bot_token,
            parse_mode=ParseMode.HTML
        )
        logger.info("Bot instance created successfully")
        
        # Устанавливаем команды бота
        try:
            await set_bot_commands(bot)
            logger.info("Bot commands set successfully")
        except Exception as e:
            logger.error(f"Error setting bot commands: {e}", exc_info=True)
        
        # Создаем диспетчер
        dp = create_dispatcher()
        logger.info("Dispatcher created successfully")
        
        # Регистрируем экземпляр бота для использования в bot_notifier
        # Это позволяет отправлять уведомления из других частей приложения
        from bot_notifier import set_bot_instance
        set_bot_instance(bot)
        logger.info("Bot instance registered in bot_notifier")
        
        # Запускаем polling
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise
    finally:
        if bot:
            await bot.session.close()
            logger.info("Bot session closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

