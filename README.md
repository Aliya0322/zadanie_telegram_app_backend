# Telegram Mini App Backend

Бэкенд для Telegram Mini App с использованием FastAPI, PostgreSQL, APScheduler и Aiogram.

## Особенности

- ✅ Проверка Telegram initData для аутентификации
- ✅ CRUD операции для групп, домашних заданий и расписания
- ✅ Фоновые задачи с APScheduler для отправки уведомлений
- ✅ Поддержка часовых поясов
- ✅ Роли пользователей (Учитель/Ученик)

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

3. **Заполните переменные окружения в файле `.env`:**

   **DATABASE_URL** - строка подключения к PostgreSQL:
   ```
   DATABASE_URL=postgresql://username:password@localhost:5432/telegram_app_db
   ```
   Замените:
   - `username` - имя пользователя PostgreSQL (обычно `postgres`)
   - `password` - пароль от PostgreSQL
   - `localhost:5432` - хост и порт БД (по умолчанию localhost:5432)
   - `telegram_app_db` - имя базы данных

   **BOT_TOKEN** - токен бота от @BotFather:
   ```
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   Как получить:
   1. Откройте Telegram и найдите бота @BotFather
   2. Отправьте команду `/newbot` или `/token`
   3. Следуйте инструкциям для создания бота
   4. Скопируйте полученный токен

   **BOT_SECRET** - секретный ключ для проверки initData:
   ```
   BOT_SECRET=your_bot_secret_for_initdata_verification
   ```
   Обычно это тот же токен, что и `BOT_TOKEN`, но можно использовать отдельный секрет.

4. Создайте базу данных PostgreSQL:
```bash
createdb telegram_app_db
# или используйте init_db.sql для ручной инициализации
```

5. Примените миграции базы данных:
```bash
# Активируйте виртуальное окружение (если используете)
source venv/bin/activate

# Примените миграции
alembic upgrade head
```

6. Запустите приложение:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Примечание:** Для первого запуска создайте начальную миграцию:
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## API Эндпоинты

Все эндпоинты используют версию `/api/v1/`

### Аутентификация

- `POST /api/v1/auth/login` - Первичная регистрация/авторизация (принимает initData в заголовке)
- `GET /api/v1/auth/me` - Получить информацию о текущем пользователе
- `POST /api/v1/auth/update-role` - Обновить роль пользователя (для регистрации как учитель)

### Пользователь

- `GET /api/v1/user/dashboard` - Получить данные для главного экрана:
  - user_role (Teacher/Student)
  - Список групп
  - Расписание на сегодня
  - Активные домашние задания
- `GET /api/v1/user/schedule` - Получить полное расписание и активные ДЗ

### Группы

- `POST /api/v1/groups/` - Создать новую группу (только для учителей)
- `GET /api/v1/groups/` - Получить список групп пользователя

### Домашние задания

- `POST /api/v1/homework/` - Создать домашнее задание (учитель)
  - Принимает: `group_id`, `description`, `deadline`
  - Триггерирует планировщик для отправки уведомлений
- `POST /api/v1/homework/{homework_id}/complete` - Отметить задание как выполненное (ученик)

## Аутентификация

Все запросы должны содержать заголовок:
```
X-Telegram-Init-Data: <initData от Telegram>
```

Бэкенд автоматически проверяет валидность initData и идентифицирует пользователя. При первом входе пользователь автоматически создается в базе данных с ролью "student" по умолчанию.

## Структура базы данных

- `users` - пользователи (учителя и ученики)
- `groups` - группы
- `group_members` - участники групп
- `homework` - домашние задания
- `homework_completions` - выполненные задания
- `schedule` - расписание занятий

## Фоновые задачи

APScheduler автоматически планирует отправку напоминаний о домашних заданиях за 1 час до дедлайна. Напоминания отправляются через Aiogram всем ученикам группы.

## Безопасность

API защищен криптографической проверкой Telegram initData:
- ✅ Проверка HMAC-SHA256 подписи
- ✅ Проверка срока действия (не старше 24 часов)
- ✅ Защита от timing attacks
- ✅ Автоматическое логирование попыток аутентификации

Подробнее: [SECURITY.md](SECURITY.md)

## Миграции базы данных

Проект использует Alembic для управления миграциями:

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "описание изменений"

# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1
```

Подробнее: [MIGRATIONS.md](MIGRATIONS.md)

