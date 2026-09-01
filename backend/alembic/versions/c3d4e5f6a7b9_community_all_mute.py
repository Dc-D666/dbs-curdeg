"""频道全员禁言字段：communities.all_muted_until。

Revision ID: c3d4e5f6a7b9
Revises: b2f3d4e5f6a8
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b9'
down_revision: Union[str, Sequence[str], None] = 'b2f3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("communities", sa.Column("all_muted_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("communities", "all_muted_until")