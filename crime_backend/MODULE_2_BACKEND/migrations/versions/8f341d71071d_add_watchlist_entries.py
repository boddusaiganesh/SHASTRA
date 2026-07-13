"""add_watchlist_entries

Revision ID: 8f341d71071d
Revises: 7e230c60960c
Create Date: 2026-07-13 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '8f341d71071d'
down_revision: Union[str, Sequence[str], None] = '7e230c60960c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('watchlist_entries',
    sa.Column('watch_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_label', sa.String(length=300), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('watch_id'),
    sa.UniqueConstraint('user_id', 'entity_id', name='uq_watchlist_user_entity')
    )
    op.create_index(op.f('ix_watchlist_entries_entity_id'), 'watchlist_entries', ['entity_id'], unique=False)
    op.create_index(op.f('ix_watchlist_entries_is_active'), 'watchlist_entries', ['is_active'], unique=False)
    op.create_index(op.f('ix_watchlist_entries_user_id'), 'watchlist_entries', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_watchlist_entries_user_id'), table_name='watchlist_entries')
    op.drop_index(op.f('ix_watchlist_entries_is_active'), table_name='watchlist_entries')
    op.drop_index(op.f('ix_watchlist_entries_entity_id'), table_name='watchlist_entries')
    op.drop_table('watchlist_entries')
