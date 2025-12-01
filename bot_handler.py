from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from database import SessionLocal
from models import User, UserRole
from config import settings
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем роутер для команд
router = Router()


# BotStates не используется, но оставлено для возможного расширения


def get_or_create_user(tg_id: int, db: Session) -> User:
    """Получает или создает пользователя в БД."""
    try:
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
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in get_or_create_user: {e}", exc_info=True)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in get_or_create_user: {e}", exc_info=True)
        raise


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Обработчик команды /start - перезапуск бота.
    Поддерживает Deep Linking для автоматического присоединения к группе.
    Формат: /start group_XYZ1A2B3C
    Показывает разные сообщения для учителей и учеников.
    """
    from models import Group, GroupMember
    
    # Проверяем наличие пользователя в сообщении
    if not message.from_user:
        logger.error("message.from_user is None in cmd_start")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        return
    
    # Безопасное получение имени пользователя
    user_name = message.from_user.first_name or message.from_user.username or "Пользователь"
    
    db: Session = SessionLocal()
    try:
        # Проверяем наличие ID пользователя
        if not message.from_user.id:
            logger.error("message.from_user.id is None")
            await message.answer("❌ Произошла ошибка. Попробуйте позже.")
            return
        
        user = get_or_create_user(message.from_user.id, db)
        
        # Проверяем, есть ли параметр для присоединения к группе
        command_args = message.text.split() if message.text else []
        group_token = None
        
        if len(command_args) > 1:
            # Формат: /start group_XYZ1A2B3C
            arg = command_args[1]
            if arg.startswith("group_"):
                group_token = arg.replace("group_", "")
        
        # Если передан токен группы, обрабатываем присоединение
        if group_token:
            group = db.query(Group).filter(Group.invite_code == group_token).first()
            
            if group:
                # Проверяем, не является ли пользователь учителем этой группы
                if group.teacher_id == user.id:
                    # Учитель использует свою ссылку - показываем обычное приветствие
                    await _send_welcome_message(message, user, user_name)
                else:
                    # Проверяем, не состоит ли уже ученик в группе
                    existing_member = db.query(GroupMember).filter(
                        GroupMember.group_id == group.id,
                        GroupMember.student_id == user.id
                    ).first()
                    
                    if existing_member:
                        # Уже в группе - показываем обычное приветствие
                        await _send_welcome_message(message, user, user_name)
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
                                "Вы успешно добавлены в группу!\n\n"
                                "Теперь вся учеба у вас в кармане:\n"
                                "📅 Расписание занятий.\n"
                                "📝 Домашние задания и дедлайны.\n"
                                "🔔 Напоминания, чтобы ничего не пропустить.\n\n"
                                "Чтобы посмотреть актуальные задания, нажмите кнопку ниже."
                            )
                            
                            # Создаем кнопку "Мой личный кабинет" для открытия Mini App
                            keyboard = _create_personal_cabinet_keyboard()
                            await message.answer(welcome_text, reply_markup=keyboard)
                            
                            logger.info(f"User {user.tg_id} joined group {group.id} via invite link")
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Error adding user to group: {e}", exc_info=True)
                            await message.answer(
                                f"❌ Произошла ошибка при присоединении к группе.\n"
                                f"Попробуйте позже или обратитесь к учителю."
                            )
            else:
                await message.answer(
                    f"❌ Ссылка-приглашение недействительна или группа не найдена.\n\n"
                    f"Для дополнительной информации используйте меню /help"
                )
        else:
            # Обычное приветствие без параметров
            await _send_welcome_message(message, user, user_name)
            
    except SQLAlchemyError as e:
        logger.error(f"Database error in cmd_start: {e}", exc_info=True)
        db.rollback()
        await message.answer("❌ Произошла ошибка подключения к базе данных. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()


def _create_app_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой для открытия Mini App."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    
    web_app_url = settings.frontend_domain
    keyboard_buttons = []
    
    if web_app_url and web_app_url != "https://your-frontend-domain.com":
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="🚀 Открыть приложение",
                web_app=WebAppInfo(url=web_app_url)
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None


def _create_personal_cabinet_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой 'Мой личный кабинет' для открытия Mini App."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    
    web_app_url = settings.frontend_domain
    keyboard_buttons = []
    
    if web_app_url and web_app_url != "https://your-frontend-domain.com":
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="Мой личный кабинет",
                web_app=WebAppInfo(url=web_app_url)
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None


def _create_welcome_keyboard(is_teacher: bool) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками для приветственного сообщения."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    
    buttons = []
    
    # Кнопка "Открыть Личный Кабинет"
    web_app_url = settings.frontend_domain
    if web_app_url and web_app_url != "https://your-frontend-domain.com":
        buttons.append(
            InlineKeyboardButton(
                text="Открыть Личный Кабинет",
                web_app=WebAppInfo(url=web_app_url)
            )
        )
    
    # Кнопка "Инструкция (PDF)"
    pdf_url = settings.instruction_pdf_url
    if pdf_url:
        buttons.append(
            InlineKeyboardButton(
                text="Инструкция (PDF)",
                url=pdf_url
            )
        )
    
    if not buttons:
        return None
    
    # Размещаем кнопки в два ряда, если их две
    if len(buttons) == 2:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [buttons[0]],
            [buttons[1]]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[buttons[0]]])
    
    return keyboard


async def _send_welcome_message(message: Message, user: User, user_name: str):
    """Отправляет приветственное сообщение в зависимости от роли пользователя."""
    from models import UserRole
    
    if user.role == UserRole.TEACHER:
        # Сообщение для учителя
        welcome_text = (
            "Добро пожаловать в My Class App!\n\n"
            "Вы всё еще напоминаете ученикам о домашке в личку?\n\n"
            "My Class App — это ваш цифровой ассистент, который берет рутину на себя:\n"
            "✅ Группы и ученики в одном месте.\n"
            "✅ Домашка с файлами и дедлайнами.\n"
            "✅ Авто-напоминания ученикам (они точно не забудут!).\n\n"
            "Настройте свой первый класс за 30 секунд. 👇"
        )
    else:
        # Сообщение для ученика (базовое, можно расширить позже)
        welcome_text = (
            f"Добро пожаловать, {user_name}!\n\n"
            "My Class App — это удобный помощник для учебы:\n"
            "✅ Все домашние задания в одном месте.\n"
            "✅ Автоматические напоминания о дедлайнах.\n"
            "✅ Расписание занятий всегда под рукой.\n\n"
            "Откройте Mini App, чтобы начать работу."
        )
    
    keyboard = _create_welcome_keyboard(user.role == UserRole.TEACHER)
    
    if keyboard:
        await message.answer(welcome_text, reply_markup=keyboard)
    else:
        await message.answer(welcome_text)


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
    """Показывает информацию о том, как пользоваться ботом и ссылку на инструкцию."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    help_text = (
        "Запутались? Мы поможем! 🆘\n\n"
        "My Class App интуитивно понятен, но мы подготовили подробную инструкцию для профи.\n\n"
        "В этом файле:\n"
        "• Как создать группу и пригласить учеников.\n"
        "• Как прикреплять файлы к ДЗ.\n"
        "• Как настроить расписание.\n\n"
        "Скачивайте PDF ниже 👇"
    )
    
    # Создаем кнопку "Скачать инструкцию"
    pdf_url = settings.instruction_pdf_url
    keyboard = None
    
    if pdf_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Скачать инструкцию",
                url=pdf_url
            )]
        ])
    
    if keyboard:
        await message.answer(help_text, reply_markup=keyboard)
    else:
        await message.answer(help_text)


@router.message(Command("support"))
async def cmd_support(message: Message):
    """Техподдержка."""
    support_text = (
        "🛠 Техподдержка\n\n"
        "Если у вас возникли вопросы или проблемы с работой бота, "
        "обратитесь к администратору или используйте команду /help для получения дополнительной информации.\n\n"
        "Для работы с приложением используйте команду /app."
    )
    await message.answer(support_text)


async def set_bot_commands(bot: Bot):
    """Устанавливает команды бота в меню."""
    commands = [
        BotCommand(command="start", description="Перезапуск бота"),
        BotCommand(command="app", description="Открыть Mini App"),
        BotCommand(command="help", description="Как пользоваться"),
        BotCommand(command="support", description="Техподдержка"),
    ]
    await bot.set_my_commands(commands)


def create_dispatcher() -> Dispatcher:
    """Создает и настраивает диспетчер бота."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp

