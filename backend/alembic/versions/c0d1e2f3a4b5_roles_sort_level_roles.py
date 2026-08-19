"""roles 排序权重 + 活跃等级 + 四级默认身份组数据迁移

Revision ID: c0d1e2f3a4b5
Revises: f5a6b7c8d9e0
Create Date: 2026-08-20 03:00:00.000000

变更：
- roles 加 sort（排序即权重，越小越靠前，可管理排序在后的身份组）、is_level_role（等级身份）
- members 加 level（频道内活跃等级，默认 1）
- 数据迁移：四级默认组
  - 「频道主」sort=0（恒最前）
  - 旧「管理员」→ 改名「普通管理员」，sort=2
  - 「成员」sort=3
  - 每个频道幂等插入「超级管理员」默认组 sort=1（perms = 全量 - super）
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 超级管理员默认权限：全量权限点 - super（频道主专属）
PERMS_SUPER_ADMIN = [
    "post.create", "comment.create", "top", "essence", "delete_post", "delete_comment",
    "shutup", "kick", "member_manage", "role_manage", "moderate",
]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('roles', sa.Column('sort', sa.Integer(), server_default='0', nullable=False))
    op.add_column('roles', sa.Column('is_level_role', sa.Boolean(), server_default=sa.text('0'), nullable=False))
    op.add_column('members', sa.Column('level', sa.Integer(), server_default='1', nullable=False))

    conn = op.get_bind()
    # 四级默认组：排序赋值（旧数据无 sort，默认 0，逐个覆盖）
    conn.execute(sa.text("UPDATE roles SET sort = 0 WHERE is_default = 1 AND name = '频道主'"))
    conn.execute(sa.text("UPDATE roles SET sort = 2, name = '普通管理员' WHERE is_default = 1 AND name = '管理员'"))
    conn.execute(sa.text("UPDATE roles SET sort = 3 WHERE is_default = 1 AND name = '成员'"))
    # 未命中的默认组兜底（防御：任何 is_default 组至少给 sort=10，避免权重悬空）
    conn.execute(sa.text("UPDATE roles SET sort = 10 WHERE is_default = 1 AND sort = 0 AND name <> '频道主'"))
    # 每个频道幂等插入「超级管理员」默认组
    cids = conn.execute(sa.text("SELECT id FROM communities")).fetchall()
    for (cid,) in cids:
        exists = conn.execute(
            sa.text("SELECT id FROM roles WHERE community_id = :cid AND name = '超级管理员'"),
            {"cid": cid},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO roles (community_id, name, color, level, sort, perms, is_default) "
                    "VALUES (:cid, '超级管理员', '#1a73e8', 1, 1, :perms, 1)"
                ),
                {"cid": cid, "perms": json.dumps(PERMS_SUPER_ADMIN)},
            )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('members', 'level')
    op.drop_column('roles', 'is_level_role')
    op.drop_column('roles', 'sort')
