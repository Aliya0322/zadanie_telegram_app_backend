# Docker Setup Guide

## Структура Docker Compose

Проект использует Docker Compose с тремя сервисами:

1. **postgres** - PostgreSQL база данных
2. **app** - FastAPI приложение (API сервер)
3. **bot** - Telegram Bot Handler (обработчик входящих команд)

## Быстрый старт

### 1. Создайте файл `.env`

```bash
cp .env.example .env
```

Заполните необходимые переменные:
- `BOT_TOKEN` - токен бота от @BotFather
- `BOT_SECRET` - секретный ключ (обычно тот же, что и BOT_TOKEN)
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` - настройки БД (опционально)

### 2. Запустите все сервисы

```bash
docker-compose up -d
```

### 3. Проверьте статус

```bash
docker-compose ps
```

### 4. Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Только API
docker-compose logs -f app

# Только бот
docker-compose logs -f bot
```

## Остановка

```bash
docker-compose down
```

Для удаления всех данных (включая базу данных):
```bash
docker-compose down -v
```

## Пересборка после изменений

```bash
docker-compose build
docker-compose up -d
```

## Доступ к сервисам

- **FastAPI API**: http://localhost:8000
- **API Документация**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
  - User: postgres (или из POSTGRES_USER)
  - Password: postgres (или из POSTGRES_PASSWORD)
  - Database: telegram_app_db (или из POSTGRES_DB)

## Архитектура

### FastAPI (app)
- Обрабатывает HTTP запросы от фронтенда
- Проверяет Telegram initData
- Управляет группами, домашними заданиями, расписанием
- Использует APScheduler для планирования напоминаний

### Telegram Bot (bot)
- Обрабатывает входящие команды от пользователей через Polling
- Команды: `/start`, `/app`, `/help`, `/status`, `/subscribe`, `/unsubscribe`
- Отправляет уведомления через Bot API (используется из app)

### PostgreSQL (postgres)
- Хранит все данные приложения
- Таблицы создаются автоматически при первом запуске

## Разработка

Для разработки с hot-reload:

```bash
docker-compose up
```

Изменения в коде будут автоматически подхватываться благодаря volume mount.

## Production

Для production рекомендуется:

1. Убрать `--reload` из команды в docker-compose.yml
2. Использовать переменные окружения вместо .env файла
3. Настроить правильные CORS origins
4. Использовать reverse proxy (nginx)
5. Настроить SSL/TLS

## Troubleshooting

### Бот не отвечает на команды

1. Проверьте логи: `docker-compose logs bot`
2. Убедитесь, что BOT_TOKEN правильный
3. Проверьте, что бот запущен: `docker-compose ps bot`

### Ошибки подключения к БД

1. Проверьте, что PostgreSQL запущен: `docker-compose ps postgres`
2. Проверьте DATABASE_URL в .env
3. Проверьте логи: `docker-compose logs postgres`

### Проблемы с портами

Если порты 8000 или 5432 заняты, измените их в docker-compose.yml:

```yaml
ports:
  - "8001:8000"  # Внешний:Внутренний
```

