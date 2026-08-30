# 第三方 AI 审查报告（原始存档）

> 来源：另一 AI 的数据库审查报告（2026-08-29 前后），经人工交叉验证后用于优化实施。
> 验证结论见 git 提交记录与本仓优化迁移脚本；此处保存报告原文。

---

# 项目与数据库盘点

**项目概况**:仿「腾讯频道」的课设系统 —— FastAPI + SQLAlchemy + MySQL 5.7 + Redis,Web(Vue3)+ Android 双端,已部署上线,128 个测试 [README.md](README.md)、[PROGRESS.md](PROGRESS.md)。

**数据库现状**(`guild_backup_20260829_110228.sql`,MySQL 5.7.44 dump,实测 27 张表、约 1842 行数据):

| 类别 | 表 | 行数 |
| --- | --- | --- |
| 核心内容 | posts(22列)、comments、likes、favorites、attachments | 113 / 214 / 710 / 276 / 0 |
| 社区体系 | communities、members、boards、roles、topics、follows、user_follows、join_requests | 12 / 159 / 60 / 48 / 24 / 52 / 86 / 0 |
| 风控/审核 | reports、reviews、sensitive_words | 0 / 3 / 0 |
| 通知/工具 | notifications、short_links、search_records、feed_strategies | 2 / 0 / 0 / 0 |
| 日志/统计 | ai_call_logs、op_logs、daily_stats、system_configs、ai_configs | 37 / 0 / 8 / 0 / 0 |
| 元数据 | users、alembic_version | 37 / 1 |

架构亮点:keyset 游标分页、ngram FULLTEXT 中文搜索、Redis ZSET 热度缓存、0 哨兵幂等点赞。下面按优先级给优化建议(只分析,不改代码)。

---

## P0 — 完整性约束缺失(课设硬伤)

**全库 27 张表没有任何 FOREIGN KEY**。我 grep 了后端全部 97 个 py 文件,`ForeignKey` 零匹配——关系全部是"逻辑外键"(`posts.author_id`、`comments.post_id`…)。

课设要求明确写了「**完整性约束**」的运用,这是目前最大的扣分点。具体风险:

- 删用户/删社区/删帖子后,`members`、`comments`、`likes`、`notifications` 等全部产生**孤儿行**,且没有任何报错
- 无级联语义:课程设计答辩常问「删除一个社区会发生什么」
- 业务靠应用层自检(如 `attachment_service._get_post` [attachment_service.py](backend/app/services/attachment_service.py:48)),数据层不设防

**建议**:在 SQLAlchemy 模型上声明 `ForeignKey`,alembic 迁移生成 `CONSTRAINT ... FOREIGN KEY`。设计时明确每张表的级联策略,例如:`posts.author_id → users.id` 用 RESTRICT;`likes.post_id → posts.id` 用 CASCADE;`members.community_id → communities.id` 用 CASCADE。外键同时会**自动创建索引**,可顺势替换掉下面 P1 里的一部分单列索引。

## P0 — 视图/触发器/存储过程一个都没有(课设硬伤)

课设要求「**视图、触发器、存储过程等数据库对象的综合运用**」,dump 里这三类对象全部缺席。建议补三个"能讲出故事"的对象,且都有真实业务场景:

1. **触发器维护计数器**:`posts.like_count / comment_count / favorite_count`、`communities.member_count / post_count` 目前全是应用层自增 [post.py](backend/app/models/post.py:26)。PROGRESS.md 里就记录过「测试期间误改生产数据已恢复(posts id=10 like_count)」——计数器不一致是**已经发生过的事故**。用 `AFTER INSERT/DELETE ON likes/comments/favorites/members` 触发器维护计数,既满足课设要求又根治一致性问题。顺带指出:并发下应用层 `like_count + 1` 是读-改-写非原子操作,触发器方案天然原子。
2. **视图**:`v_feed`(posts JOIN members/boards 出作者昵称、版块名)、`v_daily_stats` 或管理看板视图,前端列表查询直接 `SELECT * FROM v_feed`。
3. **存储过程**:把 keyset 分页或「帖子详情聚合(帖子+作者+计数+点赞态)」封装成存储过程,答辩时可以现场演示。

## P1 — 索引:该合的合、该删的删

当前 60 个索引全部是**单列索引**,而真实查询全是多条件过滤,`EXPLAIN` 会看到 filesort + 回表:

**需要新增的复合索引**(对应代码里的真实查询):

| 查询场景 | 过滤+排序 | 建议索引 |
| --- | --- | --- |
| 频道 feed | `community_id=? AND status=0 AND is_top=0 [AND board_id=?] ORDER BY id DESC` [post_service.py:231-243](backend/app/services/post_service.py:231) | `(community_id, status, is_top, id)` |
| 全站 feed | `status=0 AND id<? ORDER BY id DESC` [post_service.py:270](backend/app/services/post_service.py:270) | `(status, id)` |
| TA 的帖子 | `author_id=? AND status=0 AND id<? ORDER BY id DESC` [post_service.py:289](backend/app/services/post_service.py:289) | `(author_id, status, id)` |
| 评论列表 | `post_id=? AND parent_id IS NULL AND status=0 ORDER BY id` [comment_service.py:95-99](backend/app/services/comment_service.py:95) | `(post_id, status, id)` |
| 楼中楼 | `parent_id=? AND status=0 ORDER BY id` [comment_service.py:112-116](backend/app/services/comment_service.py:112) | `(parent_id, status, id)` |

**纯冗余索引**(唯一约束左前缀已被覆盖,写放大、白占空间,可删):

| 冗余索引 | 被谁覆盖 |
| --- | --- |
| `ix_likes_post_id` | `uq_like_target_user(post_id, comment_id, user_id)` 的左前缀 |
| `ix_favorites_user_id` | `uq_fav_user_post(user_id, post_id)` |
| `ix_follows_user_id` | `uq_follow_user_community(user_id, community_id)` |
| `ix_join_requests_community_id` | `uq_joinreq_community_user(community_id, user_id)` |
| `ix_members_community_id` | `uq_member_community_user(community_id, user_id)` |
| `ix_user_follows_user_id` | `uq_ufollow_uv(user_id, target_user_id)` |
| `ix_topics_community_id` | `uq_topic_community_name(community_id, name)` |

`ix_notifications_user_read(user_id, is_read, id)` 是全库设计得最好的索引,保持。`op_logs` 缺 `created_at` 索引(管理端按时间查操作日志)。

## P1 — 数据质量:ai_call_logs 的 status 语义 bug

dump 里 5 条记录 `status='ok'` 但 `error` 存着 429 限流错误。根因在 [llm_gateway.py:60-63](backend/app/ai/llm_gateway.py:60):GLM 主模型失败 → 切 DeepSeek 兜底,兜底成功就记 `status="ok"`,错误只塞进 `error` 列。语义上「最终成功」和「发生过降级」混在一个枚举里,管理端按 status 过滤时降级/限流**不可见**。建议:`status` 加一档 `'degraded'`,或拆一个 `fallback: bool` 列;`error` 存原始 JSON 是 255 varchar,建议截断或结构化。

## P1 — 结构设计:embedding 和图片存储

- **`posts.embedding` JSON 列**:语义搜索要把向量和整行帖子一起读出来,MySQL 5.7 的 JSON 不能建索引,帖子表一膨胀扫描成本暴涨。建议拆独立表 `post_embeddings(post_id PK, model, vector JSON, updated_at)`——行宽和主表解耦。答辩可以讲:MySQL 8.0 无原生向量支持(MySQL 9.0 才有 `VECTOR` 类型),课设用 JSON + 应用层余弦相似度是合理取舍,但独立成表是产品化姿势。
- **`posts.images` JSON 与 `attachments` 表职责重叠**:attachments 有完整 CRUD API [attachments.py](backend/app/api/v1/attachments.py:40) 但 0 行数据——两个"事实源"并存,建议明确:图片走 `images`,附件走 `attachments`,或合并。
- **`rich_content` + `source_markdown` 双存**:一份渲染 JSON + 一份纯文本,更新必须同步(现在更新帖子的代码要记得两个字段都写)。可接受,但答辩要能解释「source_markdown 是事实源,rich_content 是缓存视图」。
- **`users.phone` 无唯一约束**:目前登录只用 email/username,phone 不参与登录则建议改 NULL 或加唯一索引,否则将来支持手机号登录时无法保证唯一。

## P2 — 产品化/运维(答辩加分)

- **日志表无限增长**:`op_logs`、`ai_call_logs`、`search_records` 只写不删。建议按月分区(或定期归档),讲一句「日志与业务数据隔离生命周期」就是产品化思维。
- **`daily_stats` 按 `stat_date` 唯一**:设计正确,保留即可。
- **全库 utf8mb4_unicode_ci 统一**:好习惯,5.7 下注意 767 字节索引上限(当前 varchar 长度都安全,加了复合索引后仍安全)。
- **事务边界**:点赞/收藏/计数多步操作建议包在显式事务里(当前是独立请求各自提交),触发器方案落地后这条自动解决。

---

## 优先级排序(如果只做三件事)

1. **加外键约束**(RESTRICT/CASCADE 设计好)——课设硬性要求 + 根治孤儿数据
2. **补触发器维护计数器 + 1~2 个视图 + 1 个存储过程**——课设硬性要求 + 已发生过的计数事故
3. **复合索引替换冗余单列索引**(P1 表)——EXPLAIN 前后对比正好是答辩素材

一句话总结:功能完整度已经是课设天花板,数据库设计层面「对象运用(视图/触发器/存储过程)」和「完整性约束」两个课设验收点目前是空白,补齐后这份作业在数据库维度就无可挑剔了。

---

## 附：人工交叉验证勘误（实施依据，非原报告内容）

经代码级核实，原报告以下断言已修正：

1. ❌ "应用层 like_count+1 是读-改-写非原子" → 实测 `interact_service.py:158` 为 `UPDATE ... SET like_count = col + 1`（SQL 原子自增，git 7b19d68 已修复）。
2. ❌ "60 个索引全部单列" → 实有 7 个复合 UNIQUE + 1 个 FULLTEXT；准确说法是"普通二级索引全为单列"。
3. ❌ "多步操作独立请求各自提交" → `db.py:21-27` 为请求级会话，同请求内天然同事务。
4. ❌ "767 字节索引上限" → 5.7 默认 `innodb_large_prefix=ON` + DYNAMIC，上限 3072 字节。
5. ⚠️ status 语义 bug 根因精确位置是 `ai_call_log_service.py:17` 默认参数 `status="ok"`（非 llm_gateway.py:60-63）；另有新发现：37 行 tokens 字段全为 0（usage 未回填）。
6. ⚠️ phone 唯一索引有数据障碍：36/37 用户 phone=''，唯一索引直接建不起来，需先 NULL 化。
7. 🔑 触发器维护计数器会与应用层双计（应用层已维护全部计数器）；id=10 事故根因是人工误改库。落地姿势改为：**对账型触发器（delta 记入 counter_audit）+ EVENT 定时校准**，零冲突、零改码。
8. 🔑 实际代码 keyset 排序键是 `id` 而非 `created_at`，复合索引以 `(…, id)` 结尾才与代码吻合；置顶帖为独立等值查询。
9. 🔑 本项目 schema 由 alembic 管理，所有手工 DDL 必须包装成新 migration，否则下次 autogenerate 会还原全部优化。
