"""create posts/comments/likes/follows tables (阶段3 内容系统)

Revision ID: c4d5e6f7a8b9
Revises: ebeb7105e484
Create Date: 2026-08-19 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'ebeb7105e484'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('posts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('community_id', sa.BigInteger(), nullable=False),
    sa.Column('board_id', sa.BigInteger(), nullable=False),
    sa.Column('author_id', sa.BigInteger(), nullable=False),
    sa.Column('title', sa.String(length=128), nullable=False),
    sa.Column('rich_content', sa.JSON(), nullable=False),
    sa.Column('source_markdown', sa.Text(), nullable=False),
    sa.Column('images', sa.JSON(), nullable=False),
    sa.Column('like_count', sa.Integer(), nullable=False),
    sa.Column('comment_count', sa.Integer(), nullable=False),
    sa.Column('is_top', sa.Boolean(), nullable=False),
    sa.Column('is_essence', sa.Boolean(), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_author_id'), 'posts', ['author_id'], unique=False)
    op.create_index(op.f('ix_posts_board_id'), 'posts', ['board_id'], unique=False)
    op.create_index(op.f('ix_posts_community_id'), 'posts', ['community_id'], unique=False)
    op.create_table('comments',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('post_id', sa.BigInteger(), nullable=False),
    sa.Column('author_id', sa.BigInteger(), nullable=False),
    sa.Column('parent_id', sa.BigInteger(), nullable=True),
    sa.Column('reply_to_user_id', sa.BigInteger(), nullable=True),
    sa.Column('content', sa.String(length=2000), nullable=False),
    sa.Column('like_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comments_author_id'), 'comments', ['author_id'], unique=False)
    op.create_index(op.f('ix_comments_parent_id'), 'comments', ['parent_id'], unique=False)
    op.create_index(op.f('ix_comments_post_id'), 'comments', ['post_id'], unique=False)
    op.create_table('follows',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('community_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'community_id', name='uq_follow_user_community')
    )
    op.create_index(op.f('ix_follows_community_id'), 'follows', ['community_id'], unique=False)
    op.create_index(op.f('ix_follows_user_id'), 'follows', ['user_id'], unique=False)
    op.create_table('likes',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('post_id', sa.BigInteger(), nullable=False),
    sa.Column('comment_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'comment_id', 'user_id', name='uq_like_target_user')
    )
    op.create_index(op.f('ix_likes_comment_id'), 'likes', ['comment_id'], unique=False)
    op.create_index(op.f('ix_likes_post_id'), 'likes', ['post_id'], unique=False)
    op.create_index(op.f('ix_likes_user_id'), 'likes', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_likes_user_id'), table_name='likes')
    op.drop_index(op.f('ix_likes_post_id'), table_name='likes')
    op.drop_index(op.f('ix_likes_comment_id'), table_name='likes')
    op.drop_table('likes')
    op.drop_index(op.f('ix_follows_user_id'), table_name='follows')
    op.drop_index(op.f('ix_follows_community_id'), table_name='follows')
    op.drop_table('follows')
    op.drop_index(op.f('ix_comments_post_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_parent_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_author_id'), table_name='comments')
    op.drop_table('comments')
    op.drop_index(op.f('ix_posts_community_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_board_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_author_id'), table_name='posts')
    op.drop_table('posts')
    # ### end Alembic commands ###
