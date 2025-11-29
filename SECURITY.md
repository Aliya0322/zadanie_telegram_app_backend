# Руководство по безопасности API

## Аутентификация через Telegram initData

Приложение использует криптографическую проверку Telegram initData для обеспечения безопасности API.

### Как это работает

1. **Фронтенд получает initData от Telegram**
   - При открытии Mini App, Telegram предоставляет `initData` через `window.Telegram.WebApp.initData`

2. **Фронтенд отправляет initData в заголовке**
   - Каждый запрос к API должен содержать заголовок: `X-Telegram-Init-Data: <initData>`

3. **Бэкенд проверяет подпись**
   - Извлекает `hash` из initData
   - Создает `data-check-string` из всех полей кроме hash
   - Вычисляет секретный ключ: `HMAC_SHA256("WebAppData", bot_secret)`
   - Вычисляет hash: `HMAC_SHA256(secret_key, data-check-string)`
   - Сравнивает с полученным hash (используя `hmac.compare_digest` для защиты от timing attacks)

4. **Проверка срока действия**
   - Проверяет `auth_date` (не старше 24 часов)

5. **Извлечение user_id**
   - Только после успешной проверки извлекается `user_id` из JSON поля `user`

### Реализация

#### Функция верификации (`telegram_auth.py`)

```python
def verify_telegram_init_data(init_data: str) -> Optional[Dict]:
    """
    Проверяет Telegram initData согласно официальной документации Telegram.
    
    Безопасность:
    - Использует HMAC-SHA256 для проверки подписи
    - Проверяет срок действия (не старше 24 часов)
    - Использует constant-time сравнение для защиты от timing attacks
    - Логирует все ошибки для мониторинга
    """
```

#### FastAPI Dependency (`dependencies.py`)

```python
async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db)
) -> User:
    """
    Зависимость для защиты эндпоинтов.
    Автоматически проверяет initData и возвращает пользователя.
    """
```

### Использование в эндпоинтах

Все защищенные эндпоинты используют зависимость `get_current_user`:

```python
@router.get("/api/user/schedule")
async def get_user_schedule(
    current_user: User = Depends(get_current_user)
):
    # current_user гарантированно аутентифицирован
    ...
```

### Ошибки аутентификации

- **401 Unauthorized**: initData невалиден, истек срок действия, или проверка подписи не прошла
- **403 Forbidden**: Пользователь найден, но аккаунт неактивен

## Рекомендации по безопасности

### 1. Хранение секретов

✅ **Правильно:**
- Храните `BOT_SECRET` в переменных окружения (`.env` файл)
- Используйте разные секреты для development и production
- Никогда не коммитьте `.env` в git (уже в `.gitignore`)

❌ **Неправильно:**
- Хардкодить секреты в коде
- Использовать один секрет для всех окружений
- Делиться секретами публично

### 2. Защита от атак

#### Timing Attacks
- Используется `hmac.compare_digest()` вместо обычного `==`
- Обеспечивает постоянное время сравнения

#### Replay Attacks
- Проверка `auth_date` предотвращает использование старых initData
- Максимальный возраст: 24 часа

#### Injection Attacks
- Все данные из initData валидируются и экранируются
- Используется ORM (SQLAlchemy) для защиты от SQL injection

### 3. Логирование

Все попытки аутентификации логируются:
- Успешные проверки (на уровне INFO)
- Неудачные проверки (на уровне WARNING)
- Ошибки (на уровне ERROR с полным traceback)

### 4. CORS настройки

В production обязательно укажите конкретные домены:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-telegram-app-domain.com"],  # Конкретные домены
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Telegram-Init-Data"],
)
```

### 5. Rate Limiting

Рекомендуется добавить rate limiting для защиты от DDoS:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.get("/api/user/schedule")
@limiter.limit("10/minute")
async def get_user_schedule(...):
    ...
```

## Проверка безопасности

### Тестирование верификации

1. **Валидный initData** - должен пройти проверку
2. **Истекший initData** (auth_date > 24 часов) - должен вернуть 401
3. **Невалидный hash** - должен вернуть 401
4. **Отсутствующий hash** - должен вернуть 401
5. **Отсутствующий user** - должен вернуть 401

### Мониторинг

Следите за логами на предмет:
- Частых ошибок 401 (возможная атака)
- Необычных паттернов запросов
- Попыток использования старых initData

## Дополнительные меры безопасности

### HTTPS
- Всегда используйте HTTPS в production
- Telegram требует HTTPS для Mini Apps

### Валидация данных
- Все входные данные валидируются через Pydantic схемы
- ORM защищает от SQL injection

### Обновления зависимостей
- Регулярно обновляйте зависимости для исправления уязвимостей
- Используйте `pip-audit` для проверки известных уязвимостей

## Ссылки

- [Telegram Bot API - Web Apps](https://core.telegram.org/bots/webapps)
- [Telegram Mini Apps - initData](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

