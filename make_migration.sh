#!/bin/bash
# Скрипт для создания новой миграции Alembic

if [ -z "$1" ]; then
    echo "Использование: ./make_migration.sh <описание_миграции>"
    echo "Пример: ./make_migration.sh add_user_email_field"
    exit 1
fi

DESCRIPTION="$1"

# Активируем виртуальное окружение, если оно существует
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Создаем миграцию
alembic revision --autogenerate -m "$DESCRIPTION"

echo "Миграция создана! Проверьте файл в alembic/versions/"
echo "Затем выполните: alembic upgrade head"

