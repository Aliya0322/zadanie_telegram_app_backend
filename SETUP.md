# Инструкция по настройке проекта

## Шаг 1: Установка зависимостей

```bash
pip install -r requirements.txt
```

Или используйте виртуальное окружение:
```bash
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Шаг 2: Настройка базы данных PostgreSQL

### Установка PostgreSQL (если еще не установлен)

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Скачайте и установите с [официального сайта](https://www.postgresql.org/download/windows/)

### Создание базы данных

```bash
# Войдите в PostgreSQL
psql -U postgres

# Создайте базу данных
CREATE DATABASE telegram_app_db;

# Создайте пользователя (опционально)
CREATE USER telegram_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE telegram_app_db TO telegram_user;

# Выйдите
\q
```

## Шаг 3: Настройка переменных окружения

1. Создайте файл `.env` в корне проекта:
```bash
cp .env.example .env
```

2. Откройте файл `.env` и заполните следующие переменные:

### DATABASE_URL
```
DATABASE_URL=postgresql://username:password@localhost:5432/telegram_app_db
```

**Примеры:**
- Если используете пользователя `postgres` с паролем `mypassword`:
  ```
  DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/telegram_app_db
  ```

- Если создали отдельного пользователя:
  ```
  DATABASE_URL=postgresql://telegram_user:your_password@localhost:5432/telegram_app_db
  ```

### BOT_TOKEN
```
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

**Как получить токен:**
1. Откройте Telegram
2. Найдите бота [@BotFather](https://t.me/BotFather)
3. Отправьте команду `/newbot`
4. Следуйте инструкциям:
   - Введите имя бота (например: "My Homework Bot")
   - Введите username бота (должен заканчиваться на `bot`, например: `my_homework_bot`)
5. BotFather вернет токен вида `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
6. Скопируйте токен и вставьте в `.env`

**Или если бот уже создан:**
- Отправьте `/token` боту @BotFather
- Выберите нужного бота из списка
- Скопируйте токен

### BOT_SECRET
```
BOT_SECRET=your_bot_secret_for_initdata_verification
```

**Обычно используется тот же токен, что и BOT_TOKEN:**
```
BOT_SECRET=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

Или можно использовать отдельный секретный ключ для дополнительной безопасности.

## Шаг 4: Проверка настроек

Убедитесь, что файл `.env` содержит все необходимые переменные:
```bash
cat .env
```

Должно быть примерно так:
```
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/telegram_app_db
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
BOT_SECRET=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
HOST=0.0.0.0
PORT=8000
```

## Шаг 5: Запуск приложения

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: http://localhost:8000

Документация API: http://localhost:8000/docs

## Проверка работы

1. Откройте http://localhost:8000/health - должно вернуть `{"status": "ok"}`
2. Откройте http://localhost:8000/docs - должна открыться интерактивная документация API

## Важные замечания

⚠️ **Безопасность:**
- Никогда не коммитьте файл `.env` в git (он уже в `.gitignore`)
- Не делитесь токеном бота публично
- В продакшене используйте переменные окружения сервера вместо файла `.env`

⚠️ **База данных:**
- Таблицы создаются автоматически при первом запуске приложения
- Если нужно пересоздать таблицы, удалите их вручную в PostgreSQL

⚠️ **Telegram Bot:**
- Убедитесь, что бот запущен (бот должен быть активен в Telegram)
- Для отправки сообщений бот должен иметь возможность писать пользователям

