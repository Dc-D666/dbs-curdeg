"""频道事件日志表（运营中心数据源）：join/leave/visit 三事件。

Revision ID: a1e2c3d4e5f7
Revises: f9a2b4c6d8e0
Create Date: 2026-09-01

供频道主查看自己频道的运营数据（新增/退出成员数、访问人数次数）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f9a2b4c6d8e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "community_event_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("community_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("event", sa.String(length=16), nullable=False, comment="join/leave/visit"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_community_event_logs_user_id", "community_event_logs", ["user_id"], unique=False)
    op.create_index(
        "ix_ce_community_event_date", "community_event_logs",
        ["community_id", "event", "created_at"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ce_community_event_date", table_name="community_event_logs")
    op.drop_index("ix_community_event_logs_user_id", table_name="community_event_logs")
    op.drop_table("community_event_logs")