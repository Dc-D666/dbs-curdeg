"""P0 补全：新表 + 字段扩展（attachment/favorite/sensitive_word/report/system_config/ai_call_log/daily_stat/user_follow + posts/comments/topics/op_logs 字段）

Revision ID: d0e1f2a3b4c5
Revises: b6c7d8e9f0a1
Create Date: 2026-08-21 12:30:00.000000

对齐 课设技术栈推荐与实施方案.md 数据库与模块补充：
  ⑦ 帖子媒体附件、⑨ 收藏 + 用户互关、⑪ 敏感词库、⑫ 举报、⑰ AI 调用日志、
  ⑲ 统计周期、⑳ 系统基础配置；
  ⑥ posts 增 post_type/topic_id/view_count/favorite_count/share_count；
  ⑧ comments 增 comment_type/reply_count/ip_region；
  ⑩ topics 增描述/封面/规则/帖子数/热度/状态；⑱ op_logs 增请求/响应。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ---- 现有表加列 ----
    op.add_column('posts', sa.Column('post_type', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('posts', sa.Column('topic_id', sa.BigInteger(), nullable=True))
    op.add_column('posts', sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('posts', sa.Column('favorite_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('posts', sa.Column('share_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_posts_topic_id'), 'posts', ['topic_id'], unique=False)

    op.add_column('comments', sa.Column('comment_type', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('comments', sa.Column('reply_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('comments', sa.Column('ip_region', sa.String(length=64), nullable=False, server_default=''))

    op.add_column('topics', sa.Column('description', sa.String(length=255), nullable=False, server_default=''))
    op.add_column('topics', sa.Column('cover_url', sa.String(length=255), nullable=False, server_default=''))
    op.add_column('topics', sa.Column('rules', sa.String(length=500), nullable=False, server_default=''))
    op.add_column('topics', sa.Column('post_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('topics', sa.Column('heat_value', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('topics', sa.Column('status', sa.Integer(), nullable=False, server_default='0'))

    op.add_column('op_logs', sa.Column('request_params', sa.JSON(), nullable=True))
    op.add_column('op_logs', sa.Column('response_result', sa.JSON(), nullable=True))

    # ---- 新表 ----
    op.create_table('attachments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('media_type', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('url', sa.String(length=255), nullable=False),
        sa.Column('thumb_url', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('width', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('height', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_post_id'), 'attachments', ['post_id'], unique=False)

    op.create_table('favorites',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('group_name', sa.String(length=32), nullable=False, server_default='默认'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'post_id', name='uq_fav_user_post')
    )
    op.create_index(op.f('ix_favorites_user_id'), 'favorites', ['user_id'], unique=False)
    op.create_index(op.f('ix_favorites_post_id'), 'favorites', ['post_id'], unique=False)

    op.create_table('sensitive_words',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('word', sa.String(length=64), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False, server_default='其他'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sensitive_words_word'), 'sensitive_words', ['word'], unique=True)

    op.create_table('reports',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('target_type', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.BigInteger(), nullable=False),
        sa.Column('reporter_id', sa.BigInteger(), nullable=False),
        sa.Column('reason_type', sa.String(length=32), nullable=False, server_default='其他'),
        sa.Column('detail', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('status', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('handler_id', sa.BigInteger(), nullable=True),
        sa.Column('handled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_target_id'), 'reports', ['target_id'], unique=False)
    op.create_index(op.f('ix_reports_reporter_id'), 'reports', ['reporter_id'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)

    op.create_table('system_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_configs_key'), 'system_configs', ['key'], unique=True)

    op.create_table('ai_call_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('feature', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('model', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='ok'),
        sa.Column('error', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_call_logs_feature'), 'ai_call_logs', ['feature'], unique=False)
    op.create_index(op.f('ix_ai_call_logs_user_id'), 'ai_call_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_call_logs_created_at'), 'ai_call_logs', ['created_at'], unique=False)

    op.create_table('daily_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('new_members', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active_members', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('posts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('interactions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('violations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ai_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retention', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_stats_stat_date'), 'daily_stats', ['stat_date'], unique=True)

    op.create_table('user_follows',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('target_user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'target_user_id', name='uq_ufollow_uv')
    )
    op.create_index(op.f('ix_user_follows_user_id'), 'user_follows', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_follows_target_user_id'), 'user_follows', ['target_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_user_follows_target_user_id'), table_name='user_follows')
    op.drop_index(op.f('ix_user_follows_user_id'), table_name='user_follows')
    op.drop_table('user_follows')
    op.drop_index(op.f('ix_daily_stats_stat_date'), table_name='daily_stats')
    op.drop_table('daily_stats')
    op.drop_index(op.f('ix_ai_call_logs_created_at'), table_name='ai_call_logs')
    op.drop_index(op.f('ix_ai_call_logs_user_id'), table_name='ai_call_logs')
    op.drop_index(op.f('ix_ai_call_logs_feature'), table_name='ai_call_logs')
    op.drop_table('ai_call_logs')
    op.drop_index(op.f('ix_system_configs_key'), table_name='system_configs')
    op.drop_table('system_configs')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index(op.f('ix_reports_reporter_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_target_id'), table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_sensitive_words_word'), table_name='sensitive_words')
    op.drop_table('sensitive_words')
    op.drop_index(op.f('ix_favorites_post_id'), table_name='favorites')
    op.drop_index(op.f('ix_favorites_user_id'), table_name='favorites')
    op.drop_table('favorites')
    op.drop_index(op.f('ix_attachments_post_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_column('op_logs', 'response_result')
    op.drop_column('op_logs', 'request_params')
    op.drop_column('topics', 'status')
    op.drop_column('topics', 'heat_value')
    op.drop_column('topics', 'post_count')
    op.drop_column('topics', 'rules')
    op.drop_column('topics', 'cover_url')
    op.drop_column('topics', 'description')
    op.drop_column('comments', 'ip_region')
    op.drop_column('comments', 'reply_count')
    op.drop_column('comments', 'comment_type')
    op.drop_index(op.f('ix_posts_topic_id'), table_name='posts')
    op.drop_column('posts', 'share_count')
    op.drop_column('posts', 'favorite_count')
    op.drop_column('posts', 'view_count')
    op.drop_column('posts', 'topic_id')
    op.drop_column('posts', 'post_type')
