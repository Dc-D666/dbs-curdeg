"""create op_logs / search_records tables + posts FULLTEXT(ngram) index

Revision ID: f5a6b7c8d9e0
Revises: e1f2a3b4c5d6
Create Date: 2026-08-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('op_logs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('community_id', sa.BigInteger(), nullable=False),
    sa.Column('operator_id', sa.BigInteger(), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('target_type', sa.String(length=32), nullable=False),
    sa.Column('target_id', sa.BigInteger(), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_op_logs_community_id'), 'op_logs', ['community_id'], unique=False)
    op.create_index(op.f('ix_op_logs_operator_id'), 'op_logs', ['operator_id'], unique=False)
    op.create_table('search_records',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('keyword', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('community_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_records_keyword'), 'search_records', ['keyword'], unique=False)
    op.create_index(op.f('ix_search_records_created_at'), 'search_records', ['created_at'], unique=False)
    # 中文搜索索引：ngram 解析器（MySQL 5.7.6+ 内置），生产库专用；
    # 测试库（Base.metadata.create_all）无此索引，搜索服务会自动降级 LIKE 路径。
    op.execute(
        "ALTER TABLE posts ADD FULLTEXT INDEX ft_post_search (title, source_markdown) WITH PARSER ngram"
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE posts DROP INDEX ft_post_search")
    op.drop_index(op.f('ix_search_records_created_at'), table_name='search_records')
    op.drop_index(op.f('ix_search_records_keyword'), table_name='search_records')
    op.drop_table('search_records')
    op.drop_index(op.f('ix_op_logs_operator_id'), table_name='op_logs')
    op.drop_index(op.f('ix_op_logs_community_id'), table_name='op_logs')
    op.drop_table('op_logs')
    # ### end Alembic commands ###
