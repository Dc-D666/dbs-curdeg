"""create reviews / ai_configs tables + posts.embedding column (阶段 6 AI 一期)

Revision ID: b6c7d8e9f0a1
Revises: a1b2c3d4e5f6
Create Date: 2026-08-21 11:00:00.000000

阶段 6：内容审核记录表、AI 功能配置表、帖子语义向量列（RAG 用，MySQL 无
VECTOR 类型，JSON 数组存 embedding，应用层余弦相似度召回）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6c7d8e9f0a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('posts', sa.Column('embedding', sa.JSON(), nullable=True))
    op.create_table('reviews',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('content_type', sa.Integer(), nullable=False),
    sa.Column('content_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('violation_type', sa.String(length=32), nullable=False),
    sa.Column('violation_detail', sa.String(length=255), nullable=False),
    sa.Column('review_method', sa.Integer(), nullable=False),
    sa.Column('appeal_at', sa.DateTime(), nullable=True),
    sa.Column('reviewer_id', sa.BigInteger(), nullable=True),
    sa.Column('result', sa.String(length=255), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reviews_user_id'), 'reviews', ['user_id'], unique=False)
    op.create_index(op.f('ix_reviews_status'), 'reviews', ['status'], unique=False)
    op.create_table('ai_configs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('feature', sa.String(length=32), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('model', sa.String(length=64), nullable=False),
    sa.Column('params', sa.JSON(), nullable=True),
    sa.Column('prompt_template', sa.Text(), nullable=False),
    sa.Column('rate_limit', sa.Integer(), nullable=False),
    sa.Column('billing_config', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_configs_feature'), 'ai_configs', ['feature'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ai_configs_feature'), table_name='ai_configs')
    op.drop_table('ai_configs')
    op.drop_index(op.f('ix_reviews_status'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_user_id'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_column('posts', 'embedding')
    # ### end Alembic commands ###
