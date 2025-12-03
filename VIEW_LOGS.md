# Как посмотреть логи на сервере

## Если используется Docker Compose

### Просмотр логов бота
```bash
# Последние 100 строк логов бота
docker-compose logs bot --tail=100

# Логи в реальном времени (следить за новыми сообщениями)
docker-compose logs -f bot

# Все логи бота с начала
docker-compose logs bot

# Логи с временными метками
docker-compose logs -t bot
```

### Просмотр логов всех сервисов
```bash
# Все сервисы
docker-compose logs --tail=100

# В реальном времени
docker-compose logs -f
```

### Просмотр логов через docker напрямую
```bash
# Если контейнер называется telegram_app_bot
docker logs telegram_app_bot --tail=100

# В реальном времени
docker logs -f telegram_app_bot

# С временными метками
docker logs -t telegram_app_bot
```

## Если используется systemd

### Просмотр логов через journalctl
```bash
# Логи сервиса (если сервис называется telegram-bot.service)
sudo journalctl -u telegram-bot.service -n 100

# В реальном времени
sudo journalctl -u telegram-bot.service -f

# Логи за сегодня
sudo journalctl -u telegram-bot.service --since today

# Логи за последний час
sudo journalctl -u telegram-bot.service --since "1 hour ago"
```

## Если запущен напрямую через Python

### Если запущен в screen/tmux
```bash
# Список сессий screen
screen -ls

# Подключиться к сессии
screen -r <session_name>

# Список сессий tmux
tmux ls

# Подключиться к сессии tmux
tmux attach -t <session_name>
```

### Если запущен в фоне с перенаправлением вывода
```bash
# Если логи пишутся в файл (например, bot.log)
tail -f bot.log

# Последние 100 строк
tail -n 100 bot.log

# Поиск ошибок в логах
grep -i error bot.log
grep -i exception bot.log
```

## Полезные команды для поиска ошибок

### Поиск ошибок в логах Docker
```bash
# Ошибки в логах бота
docker-compose logs bot | grep -i error

# Исключения
docker-compose logs bot | grep -i exception

# Ошибки за последний час
docker-compose logs bot --since 1h | grep -i error
```

### Поиск конкретной ошибки
```bash
# Поиск по тексту "cmd_start"
docker-compose logs bot | grep "cmd_start"

# Поиск с контекстом (5 строк до и после)
docker-compose logs bot | grep -A 5 -B 5 "cmd_start"
```

## Проверка статуса сервисов

### Docker Compose
```bash
# Статус всех сервисов
docker-compose ps

# Статус конкретного сервиса
docker-compose ps bot
```

### Docker
```bash
# Список контейнеров
docker ps -a

# Статус контейнера
docker inspect telegram_app_bot | grep Status
```

## Примеры для диагностики проблемы с /start

```bash
# 1. Проверить, запущен ли бот
docker-compose ps bot

# 2. Посмотреть последние ошибки
docker-compose logs bot --tail=50 | grep -i error

# 3. Посмотреть логи при выполнении команды /start
# (выполните команду в боте, затем сразу)
docker-compose logs bot --tail=20

# 4. Поиск всех упоминаний "cmd_start"
docker-compose logs bot | grep "cmd_start"

# 5. Полные логи с деталями исключений
docker-compose logs bot --tail=100
```

## Если нужно сохранить логи в файл

```bash
# Сохранить логи в файл
docker-compose logs bot > bot_logs_$(date +%Y%m%d_%H%M%S).txt

# Или только ошибки
docker-compose logs bot | grep -i error > bot_errors_$(date +%Y%m%d_%H%M%S).txt
```













