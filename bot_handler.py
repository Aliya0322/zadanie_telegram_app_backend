from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from database import SessionLocal
from models import User, UserRole
from config import settings
from sqlalchemy.orm import Session
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем роутер для команд
router = Router()


# BotStates не используется, но оставлено для возможного расширения


def get_or_create_user(tg_id: int, db: Session) -> User:
    """Получает или создает пользователя в БД."""
    user = db.query(User).filter(User.tg_id == tg_id).first()
    if not user:
        user = User(
            tg_id=tg_id,
            role=UserRole.STUDENT,
            timezone="UTC",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user with tg_id: {tg_id}")
    return user


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Обработчик команды /start - открывает Mini App.
    Поддерживает Deep Linking для автоматического присоединения к группе.
    Формат: /start group_XYZ1A2B3C
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from models import Group, GroupMember
    
    db: Session = SessionLocal()
    try:
        user = get_or_create_user(message.from_user.id, db)
        
        # Проверяем, есть ли параметр для присоединения к группе
        command_args = message.text.split() if message.text else []
        group_token = None
        
        if len(command_args) > 1:
            # Формат: /start group_XYZ1A2B3C
            arg = command_args[1]
            if arg.startswith("group_"):
                group_token = arg.replace("group_", "")
        
        # Если передан токен группы, пытаемся добавить ученика
        if group_token:
            group = db.query(Group).filter(Group.invite_code == group_token).first()
            
            if group:
                # Проверяем, не является ли пользователь учителем этой группы
                if group.teacher_id == user.id:
                    welcome_text = (
                        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
                        f"✅ Вы являетесь учителем группы '{group.name}'.\n\n"
                        f"📱 Откройте Mini App для управления группой."
                    )
                else:
                    # Проверяем, не состоит ли уже ученик в группе
                    existing_member = db.query(GroupMember).filter(
                        GroupMember.group_id == group.id,
                        GroupMember.student_id == user.id
                    ).first()
                    
                    if existing_member:
                        welcome_text = (
                            f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
                            f"✅ Вы уже состоите в группе '{group.name}'.\n\n"
                            f"📱 Откройте Mini App для просмотра заданий."
                        )
                    else:
                        # Добавляем ученика в группу
                        try:
                            new_member = GroupMember(
                                group_id=group.id,
                                student_id=user.id
                            )
                            db.add(new_member)
                            db.commit()
                            
                            welcome_text = (
                                f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
                                f"✅ Вы успешно присоединились к группе '{group.name}'!\n\n"
                                f"📱 Откройте Mini App для просмотра заданий и расписания."
                            )
                            logger.info(f"User {user.tg_id} joined group {group.id} via invite link")
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Error adding user to group: {e}")
                            welcome_text = (
                                f"❌ Произошла ошибка при присоединении к группе.\n"
                                f"Попробуйте позже или обратитесь к учителю."
                            )
            else:
                welcome_text = (
                    f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
                    f"❌ Ссылка-приглашение недействительна или группа не найдена.\n\n"
                    f"📱 Откройте Mini App для работы с приложением."
                )
        else:
            # Обычное приветствие без параметров
            welcome_text = (
                f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
                f"📱 Для работы с приложением откройте Mini App:\n"
                f"Используйте кнопку меню или команду /app\n\n"
                f"📚 Ваша роль: {user.role.value}\n"
                f"🆔 Ваш ID: {user.tg_id}"
            )
        
        # Добавляем кнопку для открытия Mini App
        web_app_url = settings.frontend_domain  # Домен Mini App из переменных окружения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Открыть приложение",
                web_app=WebAppInfo(url=web_app_url)
            )]
        ])
        
        await message.answer(welcome_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()


@router.message(Command("app"))
async def cmd_app(message: Message):
    """Открывает Mini App."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    
    web_app_url = settings.frontend_domain  # Домен Mini App из переменных окружения
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Открыть приложение",
            web_app=WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "📱 Откройте Mini App:",
        reply_markup=keyboard
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показывает список доступных команд."""
    help_text = (
        "📋 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/app - Открыть Mini App\n"
        "/help - Показать эту справку\n"
        "/status - Проверить статус аккаунта\n"
        "/subscribe - Подписаться на уведомления\n"
        "/unsubscribe - Отписаться от уведомлений"
    )
    await message.answer(help_text)


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Показывает статус пользователя."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == message.from_user.id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден. Используйте /start")
            return
        
        status_text = (
            f"👤 Статус аккаунта:\n\n"
            f"🆔 ID: {user.tg_id}\n"
            f"👨‍🏫 Роль: {user.role.value}\n"
            f"🌍 Часовой пояс: {user.timezone}\n"
            f"✅ Активен: {'Да' if user.is_active else 'Нет'}"
        )
        
        await message.answer(status_text)
    except Exception as e:
        logger.error(f"Error in cmd_status: {e}")
        await message.answer("❌ Произошла ошибка.")
    finally:
        db.close()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    """Подписаться на уведомления."""
    db: Session = SessionLocal()
    try:
        user = get_or_create_user(message.from_user.id, db)
        user.is_active = True
        db.commit()
        
        await message.answer("✅ Вы подписаны на уведомления!")
    except Exception as e:
        logger.error(f"Error in cmd_subscribe: {e}")
        await message.answer("❌ Произошла ошибка.")
    finally:
        db.close()


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    """Отписаться от уведомлений."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == message.from_user.id).first()
        if user:
            user.is_active = False
            db.commit()
            await message.answer("❌ Вы отписаны от уведомлений.")
        else:
            await message.answer("❌ Пользователь не найден.")
    except Exception as e:
        logger.error(f"Error in cmd_unsubscribe: {e}")
        await message.answer("❌ Произошла ошибка.")
    finally:
        db.close()


async def set_bot_commands(bot: Bot):
    """Устанавливает команды бота в меню."""
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="app", description="Открыть Mini App"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="status", description="Статус аккаунта"),
        BotCommand(command="subscribe", description="Подписаться на уведомления"),
        BotCommand(command="unsubscribe", description="Отписаться от уведомлений"),
    ]
    await bot.set_my_commands(commands)


def create_dispatcher() -> Dispatcher:
    """Создает и настраивает диспетчер бота."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp

