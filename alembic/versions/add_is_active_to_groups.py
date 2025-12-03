"""add_is_active_to_groups

Revision ID: add_is_active_to_groups
Revises: change_tg_id_to_bigint
Create Date: 2024-12-02 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_is_active_to_groups'
down_revision: Union[str, None] = 'change_tg_id_to_bigint'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем колонку is_active в таблицу groups
    # Это необходимо для возможности приостановки/возобновления групп
    op.add_column('groups', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Откат: удаляем колонку is_active
    op.drop_column('groups', 'is_active')

