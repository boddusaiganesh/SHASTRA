"""add_saved_investigations

Revision ID: 9a552e82182e
Revises: 8f341d71071d
Create Date: 2026-07-13 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9a552e82182e'
down_revision: Union[str, Sequence[str], None] = '8f341d71071d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('saved_investigations',
    sa.Column('investigation_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('filters', sa.JSON(), nullable=True),
    sa.Column('board_state', sa.JSON(), nullable=True),
    sa.Column('district_id', sa.String(length=50), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['district_id'], ['districts.district_id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('investigation_id')
    )
    op.create_index(op.f('ix_saved_investigations_district_id'), 'saved_investigations', ['district_id'], unique=False)
    op.create_index(op.f('ix_saved_investigations_created_by'), 'saved_investigations', ['created_by'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_investigations_created_by'), table_name='saved_investigations')
    op.drop_index(op.f('ix_saved_investigations_district_id'), table_name='saved_investigations')
    op.drop_table('saved_investigations')
