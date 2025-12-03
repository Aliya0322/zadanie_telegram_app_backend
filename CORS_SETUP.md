# Настройка CORS для Production

## Проблема

Если вы получаете ошибку:
```
Origin https://www.myclassapp.ru is not allowed by Access-Control-Allow-Origin. Status code: 500
```

Это означает, что либо:
1. Переменная окружения `FRONTEND_DOMAIN` не установлена правильно на production сервере
2. Сервер возвращает ошибку 500, и CORS headers не добавляются

## Решение

### 1. Установите переменные окружения на production сервере

В файле `.env` на production сервере установите:

```bash
FRONTEND_DOMAIN=https://www.myclassapp.ru
```

Или, если хотите явно указать все разрешенные домены:

```bash
CORS_ORIGINS=https://www.myclassapp.ru,https://myclassapp.ru
```

### 2. Проверьте логи при запуске

При запуске приложения в логах должно быть:
```
CORS allowed origins: ['https://www.myclassapp.ru', 'https://myclassapp.ru', ...]
```

Если вы не видите `https://www.myclassapp.ru` в списке, значит переменная окружения не установлена правильно.

### 3. Тестирование CORS

Используйте тестовый endpoint для проверки:
```bash
curl -H "Origin: https://www.myclassapp.ru" https://api.myclassapp.ru/cors-test
```

Должен вернуться JSON с информацией о том, разрешен ли origin.

### 4. Проверка в браузере

Откройте консоль браузера на `https://www.myclassapp.ru` и выполните:
```javascript
fetch('https://api.myclassapp.ru/cors-test', {
  method: 'GET',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json'
  }
})
.then(r => r.json())
.then(console.log)
.catch(console.error)
```

### 5. Проверка логов сервера

В логах сервера должны быть записи:
```
CORS request from origin: https://www.myclassapp.ru, allowed: True
```

Если `allowed: False`, значит origin не в списке разрешенных.

## Важные замечания

1. **CORS middleware должен быть добавлен ПЕРЕД другими middleware** - это уже сделано в коде
2. **Глобальные обработчики исключений** добавлены для обеспечения CORS headers даже при ошибках 500
3. **Логирование CORS запросов** включено для отладки

## После изменений

После установки правильных переменных окружения:
1. Перезапустите приложение
2. Проверьте логи при запуске
3. Протестируйте запросы с фронтенда

