# 阶段 5~10 开发进度（PROGRESS.md）

> 长程会话：2026-08-20 凌晨，用户睡觉期间按「每完成一个验收点就 push 上线」节奏推进。
> 线上站点：https://guild.weaxi.cn（push 后 ssh 手动触发部署，或等 cron 3 分钟轮询）

## 里程碑总览（全部完成 ✅）

| 里程碑 | 提交 | 说明 |
|---|---|---|
| M1 阶段5·WS 通知 | `c309029` | notifications 表 + ws/manager + notify_service + 通知 API/开关 + 前端通知中心/角标/WS 客户端；线上端到端验证（评论实时推送） |
| M2 阶段5·分享短链 | `a4a827f` | share_service + /s/{code} 302 跳转 + Redis 同 IP 防刷计数 + 过期清理 + 前端分享按钮；线上验证通过 |
| M3 阶段5·Feed 热度 | `fb66089` | feed_strategies 权重 + score=like+2×comment+3×favorite+置顶 ×指数衰减 + Redis ZSET 缓存/bump + 策略 API；线上验证通过 |
| M4 阶段6·AI 一期 | `ca230fd` `f919182` `1a381e0` | LLM 网关（GLM 主+DS 兜底）+ SSE 帮写 + 审核队列/申诉 + RAG 问答 + 前端 AI 按钮/问答浮窗；线上真实 GLM 验证通过 |
| M5 阶段7~8·看板+搜索+加固 | `f384a2a` | /admin/stats 看板（前端 DashboardView）+ 搜索语义召回 + 人工审核端点 + 限流（登录/注册/验证码）；线上验证通过 |
| M6 阶段9·Android 脚手架 | `0803c63` | android/ 工程（AGP 8.5.2 + Kotlin 2.0.21 + Compose BOM，minSdk 26）：Retrofit 数据层 + 登录/首页流/帖子详情/通知/我的；待 Android Studio 构建验证 |
| M7 阶段10·答辩材料 | 本提交 | 答辩文档.md（架构/亮点/10 分钟演示脚本/问答准备）+ 交接文档更新 |

## 测试演进

77（基线）→ 94（M1）→ 104（M2）→ 111（M3）→ 121（M4）→ **128（M5，最终全量）**
- LLM 调用测试全 mock（conftest autouse fixture），绝不真实调外部 API
- 测试连服务器 MySQL 的 guild_test 库（SSH 隧道 13306/16379），事务回滚

## 踩过的坑（重要，防复发）

1. **同一时间只能跑一个 pytest 进程**（共享 guild_test 库，drop_all 互相破坏）。
2. **测试禁用 SessionLocal 直连**（backend/.env 指向生产库 guild！）——只用 client / db_session / client_ctx fixture。
3. **线上事故（已修复，f919182）**：review_loop 同步 redis brpop 跑在 asyncio 事件循环里阻塞整个服务器 → 健康检查超时 → 自动回滚 → 回滚后 alembic 版本不一致报 "Can't locate revision"。**后台任务里的 Redis/DB 阻塞调用必须 asyncio.to_thread。** 服务器曾手动 reset 到 ca230fd 修复迁移状态。
4. **GLM-4.7-Flash 是推理模型**：stream 的 content 恒空（思考在 reasoning_content）→ assist 改 chat 取回后分块模拟流式（1a381e0）。
5. SQLAlchemy 列默认值只对 INSERT 生效（瞬时对象属性 None）→ 显式兜底。
6. prompt 里 JSON 示例花括号与 str.format() 冲突 → 双花括号转义。
7. WS 断线清理异步 → 测试轮询等待。
8. 测试需清理自建 Redis 键（feed:hot:* / share:* / rl:*）。

## 设计决策

- 审核 worker 用主进程后台任务（服务器 2C/3.5G，Redis 队列 + to_thread），模块可平移独立进程
- favorites 未实现（阶段 3 遗漏）：热度 weight_favorite 配置位保留
- 通知 ref_id 约定：帖子类=post_id、频道类=community_id；system 用 ref_id==community_id 判断跳转
- hot 分页用页码游标（前端透传字符串无感）
- 语义搜索只召回过 embedding 的帖子（不懒构建，避免搜索链路调 API）
- 限流测试环境默认关闭（共享 Redis 串扰）

## 线上备注

- 验证产生的测试帖：sdu 频道「WS端到端验证帖」「AI审核验证帖」可留作演示
- 测试期间误改生产数据已恢复（posts id=10 like_count）
- super 账号（3303188265@qq.com）密码用户自设，看板演示需用它登录
