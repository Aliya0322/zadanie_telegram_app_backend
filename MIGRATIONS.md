# Руководство по миграциям базы данных

Проект использует Alembic для управления миграциями базы данных PostgreSQL.

## Начальная настройка

### 1. Создание начальной миграции

Если база данных еще не создана, создайте начальную миграцию:

```bash
# Активируйте виртуальное окружение (если используете)
source venv/bin/activate

# Создайте начальную миграцию на основе существующих моделей
alembic revision --autogenerate -m "Initial migration"
```

Это создаст файл миграции в `alembic/versions/` с префиксом даты и времени.

### 2. Применение миграций

```bash
# Применить все миграции до последней версии
alembic upgrade head

# Применить конкретную миграцию
alembic upgrade <revision_id>

# Откатить последнюю миграцию
alembic downgrade -1

# Откатить все миграции
alembic downgrade base
```

## Работа с миграциями

### Создание новой миграции

#### Автоматическое создание (рекомендуется)

```bash
# Используйте скрипт
./make_migration.sh "описание изменений"

# Или напрямую
alembic revision --autogenerate -m "описание изменений"
```

Alembic автоматически обнаружит изменения в моделях и создаст миграцию.

#### Ручное создание

Если нужна ручная миграция:

```bash
alembic revision -m "описание изменений"
```

Затем отредактируйте созданный файл в `alembic/versions/`.

### Проверка статуса

```bash
# Показать текущую версию БД
alembic current

# Показать историю миграций
alembic history

# Показать детали конкретной миграции
alembic history -r <revision_id>
```

## Примеры использования

### Добавление нового поля в модель

1. Отредактируйте модель в `models.py`:

```python
class User(Base):
    # ... существующие поля
    email = Column(String, nullable=True)  # Новое поле
```

2. Создайте миграцию:

```bash
alembic revision --autogenerate -m "add_email_to_user"
```

3. Проверьте созданный файл миграции в `alembic/versions/`

4. Примените миграцию:

```bash
alembic upgrade head
```

### Добавление новой таблицы

1. Создайте модель в `models.py`
2. Импортируйте её в `alembic/env.py` (если нужно)
3. Создайте миграцию:

```bash
alembic revision --autogenerate -m "add_notifications_table"
```

4. Примените миграцию:

```bash
alembic upgrade head
```

## Важные замечания

⚠️ **Всегда проверяйте автоматически созданные миграции** перед применением!

Alembic может не всегда правильно определить:
- Переименование колонок (может создать удаление + добавление)
- Изменение типов данных
- Сложные изменения индексов

### Рекомендации

1. **Перед применением миграции:**
   - Проверьте SQL код в файле миграции
   - Убедитесь, что изменения корректны
   - При необходимости отредактируйте миграцию вручную

2. **В production:**
   - Всегда делайте backup базы данных перед применением миграций
   - Тестируйте миграции на staging окружении
   - Применяйте миграции в период низкой нагрузки

3. **Откат миграций:**
   - Убедитесь, что функция `downgrade()` правильно написана
   - Тестируйте откат на тестовой базе

## Структура файла миграции

```python
"""add_email_to_user

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade():
    # Код для применения миграции
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))

def downgrade():
    # Код для отката миграции
    op.drop_column('users', 'email')
```

## Интеграция с Docker

В Docker контейнере миграции можно применять автоматически при старте:

```dockerfile
# В Dockerfile или docker-compose.yml
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

Или в отдельном init скрипте:

```bash
#!/bin/bash
set -e
echo "Running migrations..."
alembic upgrade head
echo "Starting application..."
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Ошибка: "Target database is not up to date"

```bash
# Проверьте текущую версию
alembic current

# Примените все миграции
alembic upgrade head
```

### Ошибка: "Can't locate revision identified by 'xyz'"

Это означает, что история миграций не синхронизирована. Решение:

1. Проверьте файлы в `alembic/versions/`
2. Убедитесь, что все миграции присутствуют
3. При необходимости отредактируйте `down_revision` в проблемной миграции

### Откат проблемной миграции

```bash
# Откатить последнюю миграцию
alembic downgrade -1

# Исправить миграцию
# Затем применить снова
alembic upgrade head
```

