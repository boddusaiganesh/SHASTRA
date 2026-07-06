"""Add Evidence model

Revision ID: da5e74d0c8d1
Revises: 
Create Date: 2026-07-06 11:58:34.309392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'da5e74d0c8d1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('evidence',
    sa.Column('evidence_id', sa.UUID(), nullable=False),
    sa.Column('crime_id', sa.UUID(), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['crime_id'], ['crimes.crime_id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('evidence_id')
    )
    op.create_index(op.f('ix_evidence_crime_id'), 'evidence', ['crime_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evidence_crime_id'), table_name='evidence')
    op.drop_table('evidence')
