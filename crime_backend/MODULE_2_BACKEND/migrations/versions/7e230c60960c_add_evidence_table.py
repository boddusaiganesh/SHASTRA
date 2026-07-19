"""add_evidence_table

Revision ID: 7e230c60960c
Revises: 588535cb0590
Create Date: 2026-07-08 17:14:06.472554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e230c60960c'
down_revision: Union[str, Sequence[str], None] = '588535cb0590'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: both tables are already created by the baseline migration."""
    pass


def downgrade() -> None:
    """No-op."""
    pass
