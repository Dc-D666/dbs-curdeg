"""数据库综合优化（课设验收点补齐）：外键 / 视图 / 触发器 / 存储过程 / 函数 / 事件 / 索引 / 拆表

Revision ID: f9a2b4c6d8e0
Revises: d0e1f2a3b4c5
Create Date: 2026-08-29

对应三轮数据库审查报告的落地迁移（详见 AI审查报告3_数据库优化.md 附录勘误）：

A. 完整性约束（课设硬性要求）
   - 45 个外键 + 级联策略（CASCADE=从属数据 / SET NULL=弱引用 / RESTRICT=作者类强引用），覆盖全部非多态关系
   - 例外（多态引用无法外键化）：op_logs.target_id、reports.target_id、short_links.target_id、
     notifications.ref_id（多态/弱引用，ref_type 列显式标注指向）
B. 数据库对象（课设硬性要求）
   - 视图 ×6：v_post_card / v_hot_posts / v_member_profile / v_community_overview /
     v_pending_reports / v_ai_degraded_calls
   - 触发器 ×10：计数器变更 delta 记入 counter_audit（对账型，不直接改计数器，
     避免与应用层 SQLAlchemy 维护逻辑双计）
   - 存储过程 ×1：sp_reconcile_counters()（以源数据表为事实源校准 8 个计数器）
   - 函数 ×1：fn_post_heat()（热度公式 like+2*comment+3*favorite+置顶100，与 heat_service 默认权重一致）
   - 事件 ×3：ev_clean_short_links / ev_release_shutup / ev_reconcile_counters
     （需 event_scheduler=ON，deploy/docker-compose.yml 已加启动参数）
C. 索引优化（代码实证形态，keyset 以 id 结尾）
   - 新增复合索引 ×10；删除冗余/被覆盖单列索引 ×17
D. 结构拆分
   - posts.embedding(JSON) → post_embeddings 独立表（2048 维向量与主表行宽解耦）
   - likes 全多态 0 哨兵表 → post_likes / comment_likes（各带真外键+唯一约束，多态反模式清除）
   - posts 正文三大件（source_markdown/rich_content/images）→ post_contents 1:1 扩展表
     （主表行宽解耦；FULLTEXT ngram 索引随正文迁至新表，标题单列 FT 保留）
   - boards.allow_post_role_ids(JSON) → board_role_perms 关系表（身份组白名单外键化，悬空 ID 清洗）
E. 数据质量
   - users.phone 空串 → NULL + 唯一约束（为手机号登录预留唯一性）
   - comments.ip_region 误存 IP 的行清洗为空串（语义恢复为“属地文本”）
   - ai_call_logs.error 加宽 255→512；status 枚举扩 'degraded'（应用层同步改）
   - notifications 加 ref_type 列（显式化 ref_id 指向：post/comment/community/user）

downgrade 按依赖逆序完整回滚（含向量数据回填 posts.embedding）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9a2b4c6d8e0'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# SQL 片段
# ---------------------------------------------------------------------------

# 新增复合索引：(表, 索引名, 列)
NEW_INDEXES = [
    ("posts", "ix_posts_community_status_top_id", ["community_id", "status", "is_top", "id"]),
    ("posts", "ix_posts_board_status_top_id", ["board_id", "status", "is_top", "id"]),
    ("posts", "ix_posts_status_id", ["status", "id"]),
    ("posts", "ix_posts_author_status_id", ["author_id", "status", "id"]),
    ("comments", "ix_comments_post_status_id", ["post_id", "status", "id"]),
    ("comments", "ix_comments_parent_status_id", ["parent_id", "status", "id"]),
    ("op_logs", "ix_op_logs_community_created", ["community_id", "created_at"]),
    ("ai_call_logs", "ix_ai_call_logs_feature_created", ["feature", "created_at"]),
    ("search_records", "ix_search_records_keyword_created", ["keyword", "created_at"]),
    ("reports", "ix_reports_target", ["target_type", "target_id"]),
]

# 删除索引：8 个被唯一键左前缀覆盖的冗余索引 + 9 个被新复合索引覆盖的单列索引
DROP_INDEXES = [
    ("favorites", "ix_favorites_user_id"),
    ("follows", "ix_follows_user_id"),
    ("user_follows", "ix_user_follows_user_id"),
    ("members", "ix_members_community_id"),
    ("join_requests", "ix_join_requests_community_id"),
    ("topics", "ix_topics_community_id"),
    ("notifications", "ix_notifications_user_id"),
    ("posts", "ix_posts_community_id"),
    ("posts", "ix_posts_board_id"),
    ("posts", "ix_posts_author_id"),
    ("comments", "ix_comments_post_id"),
    ("comments", "ix_comments_parent_id"),
    ("op_logs", "ix_op_logs_community_id"),
    ("ai_call_logs", "ix_ai_call_logs_feature"),
    ("search_records", "ix_search_records_keyword"),
    ("reports", "ix_reports_target_id"),
]

# 外键：(表, 约束名, 列, 父表.父列, ON DELETE)
FOREIGN_KEYS = [
    ("boards", "fk_boards_community", "community_id", "communities.id", "CASCADE"),
    ("posts", "fk_posts_community", "community_id", "communities.id", "CASCADE"),
    ("posts", "fk_posts_board", "board_id", "boards.id", "CASCADE"),
    ("posts", "fk_posts_author", "author_id", "users.id", "RESTRICT"),
    ("posts", "fk_posts_topic", "topic_id", "topics.id", "SET NULL"),
    ("attachments", "fk_attachments_post", "post_id", "posts.id", "CASCADE"),
    ("comments", "fk_comments_post", "post_id", "posts.id", "CASCADE"),
    ("comments", "fk_comments_author", "author_id", "users.id", "RESTRICT"),
    ("comments", "fk_comments_parent", "parent_id", "comments.id", "CASCADE"),
    ("comments", "fk_comments_reply_to_user", "reply_to_user_id", "users.id", "SET NULL"),
    ("favorites", "fk_favorites_user", "user_id", "users.id", "CASCADE"),
    ("favorites", "fk_favorites_post", "post_id", "posts.id", "CASCADE"),
    ("follows", "fk_follows_user", "user_id", "users.id", "CASCADE"),
    ("follows", "fk_follows_community", "community_id", "communities.id", "CASCADE"),
    ("user_follows", "fk_user_follows_user", "user_id", "users.id", "CASCADE"),
    ("user_follows", "fk_user_follows_target_user", "target_user_id", "users.id", "CASCADE"),
    ("members", "fk_members_community", "community_id", "communities.id", "CASCADE"),
    ("members", "fk_members_user", "user_id", "users.id", "CASCADE"),
    ("members", "fk_members_role", "role_id", "roles.id", "SET NULL"),
    ("roles", "fk_roles_community", "community_id", "communities.id", "CASCADE"),
    ("topics", "fk_topics_community", "community_id", "communities.id", "CASCADE"),
    ("topics", "fk_topics_creator", "creator_id", "users.id", "RESTRICT"),
    ("join_requests", "fk_join_requests_community", "community_id", "communities.id", "CASCADE"),
    ("join_requests", "fk_join_requests_user", "user_id", "users.id", "CASCADE"),
    ("join_requests", "fk_join_requests_handler", "handler_id", "users.id", "SET NULL"),
    ("notifications", "fk_notifications_user", "user_id", "users.id", "CASCADE"),
    ("notifications", "fk_notifications_actor", "actor_id", "users.id", "SET NULL"),
    ("notifications", "fk_notifications_community", "community_id", "communities.id", "CASCADE"),
    ("op_logs", "fk_op_logs_community", "community_id", "communities.id", "CASCADE"),
    ("op_logs", "fk_op_logs_operator", "operator_id", "users.id", "RESTRICT"),
    ("reports", "fk_reports_reporter", "reporter_id", "users.id", "RESTRICT"),
    ("reports", "fk_reports_handler", "handler_id", "users.id", "SET NULL"),
    ("reviews", "fk_reviews_user", "user_id", "users.id", "CASCADE"),
    ("short_links", "fk_short_links_creator", "creator_id", "users.id", "RESTRICT"),
    ("search_records", "fk_search_records_user", "user_id", "users.id", "SET NULL"),
    ("search_records", "fk_search_records_community", "community_id", "communities.id", "SET NULL"),
    ("ai_call_logs", "fk_ai_call_logs_user", "user_id", "users.id", "SET NULL"),
]

# 对账型触发器：所有计数器变更记 delta 台账（不直接改计数器，防与应用层双计）
# 08-29 二轮审查：likes 拆为 post_likes/comment_likes 后，触发器不再需要分支判断
TRIGGERS = [
    ("trg_post_likes_ai", """
        CREATE TRIGGER trg_post_likes_ai AFTER INSERT ON post_likes FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('post_likes', NEW.post_id, 'posts.like_count', 1)
    """),
    ("trg_post_likes_ad", """
        CREATE TRIGGER trg_post_likes_ad AFTER DELETE ON post_likes FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('post_likes', OLD.post_id, 'posts.like_count', -1)
    """),
    ("trg_comment_likes_ai", """
        CREATE TRIGGER trg_comment_likes_ai AFTER INSERT ON comment_likes FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('comment_likes', NEW.comment_id, 'comments.like_count', 1)
    """),
    ("trg_comment_likes_ad", """
        CREATE TRIGGER trg_comment_likes_ad AFTER DELETE ON comment_likes FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('comment_likes', OLD.comment_id, 'comments.like_count', -1)
    """),
    ("trg_favorites_ai", """
        CREATE TRIGGER trg_favorites_ai AFTER INSERT ON favorites FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('favorites', NEW.post_id, 'posts.favorite_count', 1)
    """),
    ("trg_favorites_ad", """
        CREATE TRIGGER trg_favorites_ad AFTER DELETE ON favorites FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('favorites', OLD.post_id, 'posts.favorite_count', -1)
    """),
    ("trg_comments_ai", """
        CREATE TRIGGER trg_comments_ai AFTER INSERT ON comments FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('comments', NEW.post_id, 'posts.comment_count',
                IF(NEW.status = 0, 1, 0))
    """),
    ("trg_comments_au", """
        CREATE TRIGGER trg_comments_au AFTER UPDATE ON comments FOR EACH ROW
        BEGIN
          IF OLD.status = 0 AND NEW.status <> 0 THEN
            INSERT INTO counter_audit (tbl, target_id, col, delta)
            VALUES ('comments', NEW.post_id, 'posts.comment_count', -1);
          END IF;
          IF OLD.status <> 0 AND NEW.status = 0 THEN
            INSERT INTO counter_audit (tbl, target_id, col, delta)
            VALUES ('comments', NEW.post_id, 'posts.comment_count', 1);
          END IF;
        END
    """),
    ("trg_comments_ad", """
        CREATE TRIGGER trg_comments_ad AFTER DELETE ON comments FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('comments', OLD.post_id, 'posts.comment_count',
                IF(OLD.status = 0, -1, 0))
    """),
    ("trg_members_ai", """
        CREATE TRIGGER trg_members_ai AFTER INSERT ON members FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('members', NEW.community_id, 'communities.member_count', 1)
    """),
    ("trg_members_ad", """
        CREATE TRIGGER trg_members_ad AFTER DELETE ON members FOR EACH ROW
        INSERT INTO counter_audit (tbl, target_id, col, delta)
        VALUES ('members', OLD.community_id, 'communities.member_count', -1)
    """),
    ("trg_posts_au", """
        CREATE TRIGGER trg_posts_au AFTER UPDATE ON posts FOR EACH ROW
        BEGIN
          IF OLD.status = 0 AND NEW.status = 1 THEN
            INSERT INTO counter_audit (tbl, target_id, col, delta)
            VALUES ('posts', NEW.community_id, 'communities.post_count', -1);
            IF NEW.topic_id IS NOT NULL THEN
              INSERT INTO counter_audit (tbl, target_id, col, delta)
              VALUES ('posts', NEW.topic_id, 'topics.post_count', -1);
            END IF;
          END IF;
          IF OLD.status = 1 AND NEW.status = 0 THEN
            INSERT INTO counter_audit (tbl, target_id, col, delta)
            VALUES ('posts', NEW.community_id, 'communities.post_count', 1);
            IF NEW.topic_id IS NOT NULL THEN
              INSERT INTO counter_audit (tbl, target_id, col, delta)
              VALUES ('posts', NEW.topic_id, 'topics.post_count', 1);
            END IF;
          END IF;
        END
    """),
]

# 视图
VIEWS = [
    ("v_post_card", """
        CREATE VIEW v_post_card AS
        SELECT p.id, p.community_id, c.name AS community_name, c.number AS community_number,
               p.board_id, b.name AS board_name,
               p.author_id, u.nickname AS author_nickname, u.avatar_url AS author_avatar,
               p.title, p.post_type, p.topic_id,
               p.like_count, p.comment_count, p.view_count, p.favorite_count,
               p.is_top, p.is_essence, p.status, p.created_at
        FROM posts p
        JOIN communities c ON c.id = p.community_id
        JOIN boards b ON b.id = p.board_id
        JOIN users u ON u.id = p.author_id
    """),
    ("v_hot_posts", """
        CREATE VIEW v_hot_posts AS
        SELECT p.id, p.community_id, p.board_id, p.title, p.like_count, p.comment_count,
               p.favorite_count, p.is_top, p.created_at,
               (p.like_count + 2 * p.comment_count + 3 * p.favorite_count
                + IF(p.is_top, 100, 0)) AS heat
        FROM posts p
        WHERE p.status = 0
    """),
    ("v_member_profile", """
        CREATE VIEW v_member_profile AS
        SELECT m.id, m.community_id, m.user_id,
               u.nickname AS user_nickname, u.avatar_url AS user_avatar,
               m.nickname AS member_nickname, m.member_type, m.level, m.join_time,
               m.shutup_expire_at, m.is_blocked, m.last_active_at,
               r.id AS role_id, r.name AS role_name, r.color AS role_color, r.sort AS role_sort
        FROM members m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN roles r ON r.id = m.role_id
    """),
    ("v_community_overview", """
        CREATE VIEW v_community_overview AS
        SELECT c.id, c.number, c.name, c.member_count, c.post_count, c.status,
               (SELECT COUNT(*) FROM members m WHERE m.community_id = c.id) AS actual_members,
               (SELECT COUNT(*) FROM posts p WHERE p.community_id = c.id AND p.status <> 1) AS actual_posts
        FROM communities c
    """),
    ("v_pending_reports", """
        CREATE VIEW v_pending_reports AS
        SELECT r.id, r.target_type, r.target_id, r.reporter_id, u.nickname AS reporter_nickname,
               r.reason_type, r.detail, r.status, r.created_at
        FROM reports r
        JOIN users u ON u.id = r.reporter_id
        WHERE r.status IN (0, 1)
    """),
    ("v_ai_degraded_calls", """
        CREATE VIEW v_ai_degraded_calls AS
        SELECT id, feature, user_id, model, prompt_tokens, completion_tokens,
               latency_ms, status, error, created_at
        FROM ai_call_logs
        WHERE status <> 'ok' OR error <> ''
    """),
]

# 事件（需 event_scheduler=ON 才会调度执行，创建本身不需要）
EVENTS = [
    ("ev_clean_short_links", """
        CREATE EVENT ev_clean_short_links
        ON SCHEDULE EVERY 1 DAY
        STARTS TIMESTAMP(CURRENT_DATE) + INTERVAL 1 DAY + INTERVAL 4 HOUR
        DO DELETE FROM short_links
         WHERE expires_at IS NOT NULL AND expires_at < NOW()
    """),
    ("ev_release_shutup", """
        CREATE EVENT ev_release_shutup
        ON SCHEDULE EVERY 1 HOUR
        STARTS TIMESTAMP(CURRENT_DATE) + INTERVAL 1 HOUR
        DO UPDATE members SET shutup_expire_at = NULL
         WHERE shutup_expire_at IS NOT NULL AND shutup_expire_at < NOW()
    """),
    ("ev_reconcile_counters", """
        CREATE EVENT ev_reconcile_counters
        ON SCHEDULE EVERY 1 DAY
        STARTS TIMESTAMP(CURRENT_DATE) + INTERVAL 1 DAY + INTERVAL 5 HOUR
        DO BEGIN
          CALL sp_reconcile_counters();
          DELETE FROM counter_audit WHERE created_at < NOW() - INTERVAL 90 DAY;
        END
    """),
    ("ev_clean_notifications", """
        CREATE EVENT ev_clean_notifications
        ON SCHEDULE EVERY 1 DAY
        STARTS TIMESTAMP(CURRENT_DATE) + INTERVAL 1 DAY + INTERVAL 4 HOUR + INTERVAL 30 MINUTE
        DO DELETE FROM notifications
         WHERE is_read = 1 AND created_at < NOW() - INTERVAL 90 DAY
    """),
]


def _create_function_sql() -> str:
    """热度函数（权重与 heat_service.DEFAULT_STRATEGY 一致：1/2/3/置顶100）。"""
    return """
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
    """


def _create_reconcile_proc_sql() -> str:
    """计数器对账：以源数据表为事实源校准 9 个冗余计数器（幂等，可 EVENT 定时驱动）。

    口径与 post/comment/community 服务层的维护逻辑一致：
    - like_count   = post_likes / comment_likes 物理行数（08-29 拆表后两表各自对齐）
    - favorite_count = favorites 物理行数
    - comment_count  = status=0 的评论行数（软删已扣减）
    - reply_count    = status=0 的楼中楼行数
    - member_count   = members 物理行数
    - post_count     = status<>1 的帖子行数（封禁 status=2 不扣减，与 review 流程一致）
    - heat_value     = 全部状态帖子行数（历史累计热度：发帖 +1 永不回减）
    """
    return """
        CREATE PROCEDURE sp_reconcile_counters()
        BEGIN
          UPDATE posts p
          LEFT JOIN (SELECT post_id, COUNT(*) c FROM post_likes GROUP BY post_id) l
            ON l.post_id = p.id
          SET p.like_count = COALESCE(l.c, 0)
          WHERE p.like_count <> COALESCE(l.c, 0);

          UPDATE posts p
          LEFT JOIN (SELECT post_id, COUNT(*) c FROM favorites GROUP BY post_id) f
            ON f.post_id = p.id
          SET p.favorite_count = COALESCE(f.c, 0)
          WHERE p.favorite_count <> COALESCE(f.c, 0);

          UPDATE posts p
          LEFT JOIN (SELECT post_id, COUNT(*) c FROM comments WHERE status = 0 GROUP BY post_id) cm
            ON cm.post_id = p.id
          SET p.comment_count = COALESCE(cm.c, 0)
          WHERE p.comment_count <> COALESCE(cm.c, 0);

          UPDATE comments c
          LEFT JOIN (SELECT parent_id, COUNT(*) c FROM comments
                      WHERE status = 0 AND parent_id IS NOT NULL GROUP BY parent_id) r
            ON r.parent_id = c.id
          SET c.reply_count = COALESCE(r.c, 0)
          WHERE c.reply_count <> COALESCE(r.c, 0);

          UPDATE comments c
          LEFT JOIN (SELECT comment_id, COUNT(*) c FROM comment_likes GROUP BY comment_id) l
            ON l.comment_id = c.id
          SET c.like_count = COALESCE(l.c, 0)
          WHERE c.like_count <> COALESCE(l.c, 0);

          UPDATE communities c
          LEFT JOIN (SELECT community_id, COUNT(*) c FROM members GROUP BY community_id) m
            ON m.community_id = c.id
          SET c.member_count = COALESCE(m.c, 0)
          WHERE c.member_count <> COALESCE(m.c, 0);

          UPDATE communities c
          LEFT JOIN (SELECT community_id, COUNT(*) c FROM posts WHERE status <> 1 GROUP BY community_id) p
            ON p.community_id = c.id
          SET c.post_count = COALESCE(p.c, 0)
          WHERE c.post_count <> COALESCE(p.c, 0);

          UPDATE topics t
          LEFT JOIN (SELECT topic_id, COUNT(*) c FROM posts
                      WHERE topic_id IS NOT NULL GROUP BY topic_id) tp
            ON tp.topic_id = t.id
          SET t.heat_value = COALESCE(tp.c, 0)
          WHERE t.heat_value <> COALESCE(tp.c, 0);

          UPDATE topics t
          LEFT JOIN (SELECT topic_id, COUNT(*) c FROM posts
                      WHERE topic_id IS NOT NULL AND status <> 1 GROUP BY topic_id) tp
            ON tp.topic_id = t.id
          SET t.post_count = COALESCE(tp.c, 0)
          WHERE t.post_count <> COALESCE(tp.c, 0);
        END
    """


def upgrade() -> None:
    # ================= D. 向量拆表（先做，后续 FK 挂新表） =================
    op.create_table(
        "post_embeddings",
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False, server_default="embedding-3"),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], name="fk_post_embeddings_post",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
    )
    op.execute("""
        INSERT INTO post_embeddings (post_id, model, vector)
        SELECT id, 'embedding-3', embedding FROM posts WHERE embedding IS NOT NULL
    """)
    op.drop_column("posts", "embedding")

    # ============ D2. 拆表二批：likes 拆分 / posts 正文垂直拆分 / 版块白名单规范化 ============
    # --- A. likes 全多态 0 哨兵表 → post_likes + comment_likes（外键+唯一约束完整化） ---
    op.create_table(
        "post_likes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], name="fk_post_likes_post", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_post_likes_user", ondelete="CASCADE"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
        mysql_engine="InnoDB",
    )
    op.create_table(
        "comment_likes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("comment_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], name="fk_comment_likes_comment", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_comment_likes_user", ondelete="CASCADE"),
        sa.UniqueConstraint("comment_id", "user_id", name="uq_comment_like_comment_user"),
        mysql_engine="InnoDB",
    )
    op.execute(
        "INSERT INTO post_likes (post_id, user_id, created_at) "
        "SELECT post_id, user_id, created_at FROM likes WHERE comment_id = 0"
    )
    op.execute(
        "INSERT INTO comment_likes (comment_id, user_id, created_at) "
        "SELECT comment_id, user_id, created_at FROM likes WHERE comment_id <> 0"
    )
    op.drop_table("likes")

    # --- B. posts 正文三大件 → post_contents 1:1 扩展表（行宽解耦 + FULLTEXT 迁移） ---
    op.create_table(
        "post_contents",
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("source_markdown", sa.Text(), nullable=False),
        sa.Column("rich_content", sa.JSON(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], name="fk_post_contents_post", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
        mysql_engine="InnoDB",
    )
    op.execute(
        "INSERT INTO post_contents (post_id, source_markdown, rich_content, images) "
        "SELECT id, source_markdown, rich_content, images FROM posts"
    )
    # FT 索引先删后迁：原 (title, source_markdown) 复合 FT 拆为两路
    op.execute("ALTER TABLE posts DROP INDEX ft_post_search")
    op.drop_column("posts", "rich_content")
    op.drop_column("posts", "source_markdown")
    op.drop_column("posts", "images")
    op.execute("ALTER TABLE posts ADD FULLTEXT INDEX ft_post_title (title) WITH PARSER ngram")
    op.execute("ALTER TABLE post_contents ADD FULLTEXT INDEX ft_post_content (source_markdown) WITH PARSER ngram")

    # --- C. boards.allow_post_role_ids(JSON) → board_role_perms 关系表（悬空 ID 清洗） ---
    op.create_table(
        "board_role_perms",
        sa.Column("board_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], name="fk_board_role_perms_board", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_board_role_perms_role", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("board_id", "role_id"),
        mysql_engine="InnoDB",
    )
    # MySQL 5.7 无 JSON_TABLE：存储过程游标展开 JSON 数组 → 关系行
    # 已失效的身份组 ID（roles 硬删后 JSON 未清理）直接丢弃（数据质量清洗）
    op.execute("""
        CREATE PROCEDURE sp_expand_board_role_ids()
        BEGIN
          DECLARE v_board BIGINT;
          DECLARE v_len INT;
          DECLARE v_i INT;
          DECLARE v_role BIGINT;
          DECLARE v_done INT DEFAULT 0;
          DECLARE cur CURSOR FOR SELECT id FROM boards;
          DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;
          OPEN cur;
          read_loop: LOOP
            FETCH cur INTO v_board;
            IF v_done THEN LEAVE read_loop; END IF;
            SET v_len = JSON_LENGTH((SELECT allow_post_role_ids FROM boards WHERE id = v_board));
            IF v_len IS NOT NULL THEN
              SET v_i = 0;
              WHILE v_i < v_len DO
                SET v_role = CAST(JSON_EXTRACT(
                    (SELECT allow_post_role_ids FROM boards WHERE id = v_board),
                    CONCAT('$[', v_i, ']')) AS UNSIGNED);
                IF EXISTS (SELECT 1 FROM roles WHERE id = v_role) THEN
                  INSERT IGNORE INTO board_role_perms (board_id, role_id) VALUES (v_board, v_role);
                END IF;
                SET v_i = v_i + 1;
              END WHILE;
            END IF;
          END LOOP;
          CLOSE cur;
        END
    """)
    op.execute("CALL sp_expand_board_role_ids()")
    op.execute("DROP PROCEDURE sp_expand_board_role_ids")
    op.drop_column("boards", "allow_post_role_ids")

    # --- D. notifications.ref_type：显式化 ref_id 指向（消除 type→ref_id 隐式约定） ---
    op.execute("ALTER TABLE notifications ADD COLUMN ref_type VARCHAR(32) NULL DEFAULT NULL AFTER ref_id")
    op.execute("""
        UPDATE notifications SET ref_type = CASE type
            WHEN 'mention' THEN 'post'
            WHEN 'like' THEN 'post'
            WHEN 'comment' THEN 'post'
            WHEN 'follow' THEN 'community'
            ELSE NULL
        END
    """)

    # ================= E. 数据质量 =================
    # phone：先 MODIFY 允许 NULL（原列 NOT NULL，顺序反了会 1048），再空串 → NULL
    # （唯一约束允许多个 NULL，不允许多个 ''）
    op.execute("ALTER TABLE users MODIFY phone VARCHAR(32) NULL DEFAULT NULL")
    op.execute("UPDATE users SET phone = NULL WHERE phone = ''")
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])
    # ip_region：误存 IP 的行清空（字段语义 = 属地文本）
    op.execute("""
        UPDATE comments SET ip_region = ''
        WHERE ip_region REGEXP '^[0-9]{1,3}(\\\\.[0-9]{1,3}){3}$'
    """)
    # error 列加宽 255 → 512
    op.execute("ALTER TABLE ai_call_logs MODIFY error VARCHAR(512) NOT NULL DEFAULT ''")

    # ================= C. 索引：先建复合（外键可用），再挂外键，最后删冗余 =================
    for table, name, cols in NEW_INDEXES:
        op.create_index(name, table, cols, unique=False)

    # ================= A. 外键 =================
    for table, name, col, ref, ondelete in FOREIGN_KEYS:
        parent_table, parent_col = ref.split(".")
        op.create_foreign_key(name, table, parent_table, [col], [parent_col], ondelete=ondelete)

    for table, name in DROP_INDEXES:
        op.drop_index(name, table_name=table)

    # ================= B. 数据库对象 =================
    # 对账台账表（触发器写入，reconcile 前的可查证据链）
    op.create_table(
        "counter_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tbl", sa.String(32), nullable=False, comment="来源表"),
        sa.Column("target_id", sa.BigInteger(), nullable=False, comment="计数器所属父行 ID"),
        sa.Column("col", sa.String(64), nullable=False, comment="受影响计数列"),
        sa.Column("delta", sa.Integer(), nullable=False, comment="增量"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_counter_audit_col_target", "counter_audit", ["col", "target_id"])

    # 存储过程 + 函数
    op.execute(_create_reconcile_proc_sql())
    op.execute(_create_function_sql())

    # 触发器（对账型 delta 台账）
    for _, ddl in TRIGGERS:
        op.execute(ddl)

    # 视图
    for _, ddl in VIEWS:
        op.execute(ddl)

    # 事件（event_scheduler 由容器启动参数开启）
    for _, ddl in EVENTS:
        op.execute(ddl)


def downgrade() -> None:
    # ---- 逆序回滚：事件/视图/触发器/函数/存储过程 ----
    for name, _ in EVENTS:
        op.execute(f"DROP EVENT IF EXISTS {name}")
    for name, _ in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {name}")
    for name, _ in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.execute("DROP FUNCTION IF EXISTS fn_post_heat")
    op.execute("DROP PROCEDURE IF EXISTS sp_reconcile_counters")
    op.drop_index("ix_counter_audit_col_target", table_name="counter_audit")
    op.drop_table("counter_audit")

    # ---- 外键 ----
    for table, name, *_ in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")

    # ---- 索引（重建被删的单列索引 + 删除新复合索引） ----
    for table, name in DROP_INDEXES:
        cols = {
            "ix_favorites_user_id": ["user_id"], "ix_follows_user_id": ["user_id"],
            "ix_user_follows_user_id": ["user_id"],
            "ix_members_community_id": ["community_id"],
            "ix_join_requests_community_id": ["community_id"],
            "ix_topics_community_id": ["community_id"],
            "ix_notifications_user_id": ["user_id"],
            "ix_posts_community_id": ["community_id"], "ix_posts_board_id": ["board_id"],
            "ix_posts_author_id": ["author_id"], "ix_comments_post_id": ["post_id"],
            "ix_comments_parent_id": ["parent_id"],
            "ix_op_logs_community_id": ["community_id"],
            "ix_ai_call_logs_feature": ["feature"],
            "ix_search_records_keyword": ["keyword"],
            "ix_reports_target_id": ["target_id"],
        }[name]
        op.create_index(name, table, cols, unique=False)
    for table, name, _ in NEW_INDEXES:
        op.drop_index(name, table_name=table)

    # ---- 数据质量回滚 ----
    # phone 三步顺序：先解除唯一约束（多行 NULL 同转 '' 会撞 uq_users_phone 1062）→
    # 再清 NULL → 最后收紧 NOT NULL（有 NULL 时 MODIFY 会 1138）
    op.drop_constraint("uq_users_phone", "users", type_="unique")
    op.execute("UPDATE users SET phone = '' WHERE phone IS NULL")
    op.execute("ALTER TABLE users MODIFY phone VARCHAR(32) NOT NULL DEFAULT ''")
    # error 收窄前先截断（head 加宽到 512 正为容纳长错误，直接收窄会 1406）
    op.execute("UPDATE ai_call_logs SET error = LEFT(error, 255)")
    op.execute("ALTER TABLE ai_call_logs MODIFY error VARCHAR(255) NOT NULL DEFAULT ''")

    # ---- 向量拆表回滚：先加列，再回填，最后删表 ----
    op.execute("ALTER TABLE posts ADD COLUMN embedding JSON NULL AFTER is_essence")
    op.execute("""
        UPDATE posts p
        JOIN post_embeddings pe ON pe.post_id = p.id
        SET p.embedding = pe.vector
    """)
    op.drop_table("post_embeddings")

    # ---- 拆表二批回滚（逆序）：likes 拆分 / 正文垂直拆分 / 白名单规范化 / ref_type ----
    # notifications.ref_type
    op.execute("ALTER TABLE notifications DROP COLUMN ref_type")

    # boards.allow_post_role_ids：关系表聚合回 JSON（GROUP_CONCAT 拼 JSON 数组，5.7 无 JSON_ARRAYAGG）
    op.execute("ALTER TABLE boards ADD COLUMN allow_post_role_ids JSON NULL")
    op.execute("""
        UPDATE boards b
        SET b.allow_post_role_ids = COALESCE((
            SELECT CONCAT('[', GROUP_CONCAT(brp.role_id ORDER BY brp.role_id SEPARATOR ','), ']')
            FROM board_role_perms brp WHERE brp.board_id = b.id
        ), '[]')
    """)
    op.execute("ALTER TABLE boards MODIFY allow_post_role_ids JSON NOT NULL")
    op.drop_table("board_role_perms")

    # posts 正文三列：先加列（允许 NULL，避免非空无默认填充失败）→ 回填 → 收紧非空
    op.execute(
        "ALTER TABLE posts ADD COLUMN rich_content JSON NULL AFTER topic_id, "
        "ADD COLUMN source_markdown TEXT NULL AFTER rich_content, "
        "ADD COLUMN images JSON NULL AFTER source_markdown"
    )
    op.execute("""
        UPDATE posts p JOIN post_contents pc ON pc.post_id = p.id
        SET p.rich_content = pc.rich_content,
            p.source_markdown = pc.source_markdown,
            p.images = pc.images
    """)
    op.execute(
        "ALTER TABLE posts MODIFY rich_content JSON NOT NULL, "
        "MODIFY source_markdown TEXT NOT NULL, MODIFY images JSON NOT NULL"
    )
    # ft_post_content 在 post_contents 上，随表删除；posts 只需删标题 FT
    op.execute("ALTER TABLE posts DROP INDEX ft_post_title")
    op.execute("ALTER TABLE posts ADD FULLTEXT INDEX ft_post_search (title, source_markdown) WITH PARSER ngram")
    op.drop_table("post_contents")

    # likes 重建（d0e1f2a3b4c5 时刻原状：无外键，三单列索引 + 三列唯一键）
    op.create_table(
        "likes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("comment_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("post_id", "comment_id", "user_id", name="uq_like_target_user"),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_likes_post_id", "likes", ["post_id"])
    op.create_index("ix_likes_comment_id", "likes", ["comment_id"])
    op.create_index("ix_likes_user_id", "likes", ["user_id"])
    op.execute(
        "INSERT INTO likes (post_id, comment_id, user_id, created_at) "
        "SELECT post_id, 0, user_id, created_at FROM post_likes"
    )
    op.execute(
        "INSERT INTO likes (post_id, comment_id, user_id, created_at) "
        "SELECT 0, comment_id, user_id, created_at FROM comment_likes"
    )
    op.drop_table("comment_likes")
    op.drop_table("post_likes")
