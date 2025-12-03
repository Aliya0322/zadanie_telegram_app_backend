"""add_user_profile_and_meeting_link

Revision ID: add_profile_fields
Revises: 
Create Date: 2024-01-01 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_profile_fields'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user profile fields
    op.add_column('users', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('patronymic', sa.String(), nullable=True))
    op.add_column('users', sa.Column('birthdate', sa.DateTime(timezone=True), nullable=True))
    
    # Add meeting link and duration to schedule
    op.add_column('schedule', sa.Column('meeting_link', sa.String(), nullable=True))
    op.add_column('schedule', sa.Column('duration', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('schedule', 'duration')
    op.drop_column('schedule', 'meeting_link')
    op.drop_column('users', 'birthdate')
    op.drop_column('users', 'patronymic')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')

