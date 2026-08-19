"""create notifications / feed_strategies / short_links tables (阶段 5)

Revision ID: a1b2c3d4e5f6
Revises: c0d1e2f3a4b5
Create Date: 2026-08-21 10:00:00.000000

阶段 5 三张新表：通知消息（WS 推送落库）、Feed 热度策略（每频道一行）、分享短链。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('notifications',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('community_id', sa.BigInteger(), nullable=True),
    sa.Column('ref_id', sa.BigInteger(), nullable=True),
    sa.Column('title', sa.String(length=128), nullable=False),
    sa.Column('summary', sa.String(length=255), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read', 'id'], unique=False)
    op.create_table('feed_strategies',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('community_id', sa.BigInteger(), nullable=False),
    sa.Column('sort_rule', sa.Integer(), nullable=False),
    sa.Column('weight_like', sa.Integer(), nullable=False),
    sa.Column('weight_comment', sa.Integer(), nullable=False),
    sa.Column('weight_favorite', sa.Integer(), nullable=False),
    sa.Column('decay_hours', sa.Integer(), nullable=False),
    sa.Column('top_weight', sa.Integer(), nullable=False),
    sa.Column('cache_ttl', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feed_strategies_community_id'), 'feed_strategies', ['community_id'], unique=True)
    op.create_table('short_links',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('target_type', sa.Integer(), nullable=False),
    sa.Column('target_id', sa.BigInteger(), nullable=False),
    sa.Column('creator_id', sa.BigInteger(), nullable=False),
    sa.Column('visit_count', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_short_links_code'), 'short_links', ['code'], unique=True)
    op.create_index(op.f('ix_short_links_creator_id'), 'short_links', ['creator_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_short_links_creator_id'), table_name='short_links')
    op.drop_index(op.f('ix_short_links_code'), table_name='short_links')
    op.drop_table('short_links')
    op.drop_index(op.f('ix_feed_strategies_community_id'), table_name='feed_strategies')
    op.drop_table('feed_strategies')
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    # ### end Alembic commands ###
