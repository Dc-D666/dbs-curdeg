"""补充 3 处遗漏外键 + 热度口径统一（fn_post_heat / v_hot_posts 补时间衰减）。

背景（答辩风险修复）：
- feed_strategies.community_id / community_event_logs.user_id / reviews.reviewer_id
  是单目标、非多态关系，此前漏挂外键，与"45 条外键覆盖全部非多态关系"的口径不符；
- fn_post_heat / v_hot_posts 此前无时间衰减，与应用层 hot_score() 口径不一致，
  现场算一条热度两边答案不同。这里统一为与应用层 DEFAULTS（权重 1/2/3、衰减 24h、置顶 100）一致。

Revision ID: a5f6e7d8c9b0
Revises: c3d4e5f6a7b9
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a5f6e7d8c9b0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 与应用层 heat_service.DEFAULTS 一致：like*1 + comment*2 + fav*3，指数衰减 24h，置顶 +100
DECAYED_HEAT_SQL = """((p.like_count + 2 * p.comment_count + 3 * p.favorite_count)
      * EXP(-TIMESTAMPDIFF(HOUR, p.created_at, NOW()) / 24)
      + IF(p.is_top, 100, 0))"""


def upgrade() -> None:
    # ---------- ① 补 3 处遗漏外键（先清洗悬空引用，避免 ADD CONSTRAINT 失败） ----------
    op.execute(
        "DELETE fs FROM feed_strategies fs LEFT JOIN communities c ON c.id = fs.community_id "
        "WHERE c.id IS NULL"
    )
    op.execute(
        "UPDATE community_event_logs SET user_id = NULL WHERE user_id IS NOT NULL "
        "AND user_id NOT IN (SELECT id FROM users)"
    )
    op.execute(
        "UPDATE reviews SET reviewer_id = NULL WHERE reviewer_id IS NOT NULL "
        "AND reviewer_id NOT IN (SELECT id FROM users)"
    )
    op.create_foreign_key(
        "fk_feed_strategies_community", "feed_strategies", "communities",
        ["community_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_community_event_logs_user", "community_event_logs", "users",
        ["user_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reviews_reviewer", "reviews", "users",
        ["reviewer_id"], ["id"], ondelete="SET NULL",
    )

    # ---------- ② 热度口径统一：函数补时间衰减，与应用层 hot_score 一致 ----------
    op.execute("DROP FUNCTION IF EXISTS fn_post_heat")
    op.execute("""
        CREATE FUNCTION fn_post_heat(p_post_id BIGINT) RETURNS DECIMAL(18,4)
        READS SQL DATA
        DETERMINISTIC
        BEGIN
          DECLARE v_like INT;
          DECLARE v_comment INT;
          DECLARE v_fav INT;
          DECLARE v_top INT;
          DECLARE v_created DATETIME;
          SELECT like_count, comment_count, favorite_count, is_top, created_at
            INTO v_like, v_comment, v_fav, v_top, v_created
            FROM posts WHERE id = p_post_id;
          RETURN ((v_like + 2 * v_comment + 3 * v_fav)
                  * EXP(-TIMESTAMPDIFF(HOUR, v_created, NOW()) / 24)
                  + IF(v_top IS NULL, 0, IF(v_top, 100, 0)));
        END
    """)
    op.execute("DROP VIEW IF EXISTS v_hot_posts")
    op.execute(
        "CREATE VIEW v_hot_posts AS "
        "SELECT p.id, p.community_id, p.board_id, p.title, p.like_count, p.comment_count, "
        "p.favorite_count, p.is_top, p.created_at, "
        + DECAYED_HEAT_SQL + " AS heat "
        "FROM posts p WHERE p.status = 0"
    )


def downgrade() -> None:
    op.drop_constraint("fk_reviews_reviewer", "reviews", type_="foreignkey")
    op.drop_constraint("fk_community_event_logs_user", "community_event_logs", type_="foreignkey")
    op.drop_constraint("fk_feed_strategies_community", "feed_strategies", type_="foreignkey")

    # 还原无衰减口径（原 fn_post_heat / v_hot_posts）
    op.execute("DROP VIEW IF EXISTS v_hot_posts")
    op.execute(
        "CREATE VIEW v_hot_posts AS "
        "SELECT p.id, p.community_id, p.board_id, p.title, p.like_count, p.comment_count, "
        "p.favorite_count, p.is_top, p.created_at, "
        "(p.like_count + 2 * p.comment_count + 3 * p.favorite_count + IF(p.is_top, 100, 0)) AS heat "
        "FROM posts p WHERE p.status = 0"
    )
    op.execute("DROP FUNCTION IF EXISTS fn_post_heat")
    op.execute("""
        CREATE FUNCTION fn_post_heat(p_post_id BIGINT) RETURNS INT
        READS SQL DATA
        DETERMINISTIC
        BEGIN
          DECLARE v_like INT;
          DECLARE v_comment INT;
          DECLARE v_fav INT;
          DECLARE v_top INT;
          SELECT like_count, comment_count, favorite_count, is_top
            INTO v_like, v_comment, v_fav, v_top
            FROM posts WHERE id = p_post_id;
          RETURN v_like + 2 * v_comment + 3 * v_fav + IF(v_top IS NULL, 0, IF(v_top, 100, 0));
        END
    """)
