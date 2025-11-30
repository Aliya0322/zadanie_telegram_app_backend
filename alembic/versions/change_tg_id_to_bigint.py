"""change_tg_id_to_bigint

Revision ID: change_tg_id_to_bigint
Revises: add_profile_fields
Create Date: 2024-11-30 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'change_tg_id_to_bigint'
down_revision: Union[str, None] = 'add_profile_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Изменяем тип колонки tg_id с INTEGER на BIGINT
    # Это необходимо, так как Telegram user IDs могут превышать максимальное значение INTEGER (2,147,483,647)
    op.alter_column('users', 'tg_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                    existing_unique=True)


def downgrade() -> None:
    # Откат: возвращаем INTEGER (может вызвать ошибку, если есть большие значения)
    op.alter_column('users', 'tg_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    existing_unique=True)

