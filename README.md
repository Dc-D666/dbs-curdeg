# dbs-curdeg — 仿「腾讯频道」课设项目

模仿腾讯频道（QQ 频道）私域平台的大学生课设：**Web + Android 双端，共用一套 FastAPI API**。

- **后端**：Python 3.12 + FastAPI + SQLAlchemy + MySQL 5.7 + Redis 7（WebSocket 通知、AI 模块）
- **前端**：Vue3 + Vite + TypeScript（移动优先 H5 + PC 管理后台）
- **Android**：Kotlin + Jetpack Compose（独立 App，另仓/本仓 android/ 目录）
- **部署**：服务器每 3 分钟自动拉取 GitHub 最新代码并重建 —— **push 到 main 即自动上线**（最长 3 分钟生效）

> 🌐 线上地址：https://guild.weaxi.cn （HTTPS，Let's Encrypt 证书自动续期）

## 目录结构

```
├── backend/            # FastAPI 后端
│   └── app/            # main.py 入口，后续按模块拆分 auth/community/content/interact/ai/notification
├── frontend/           # Vue3 + Vite 前端（Dockerfile 多阶段：node 构建 → nginx 产物）
├── deploy/             # 生产编排：docker-compose.yml + nginx 配置 + 一键部署脚本
└── .github/workflows/  # CI/CD（push 到 main 触发部署）
```

## 本地开发

```bash
# 1. 起依赖（MySQL + Redis）
docker compose -f docker-compose.dev.yml up -d

# 2. 后端（热更新）
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 前端（热更新）
cd frontend && npm install && npm run dev
```

## 部署

```bash
# 服务器上手动一键更新（或直接 git push 由 GitHub Actions 自动执行）
cd /opt/channel && ./deploy/deploy.sh
```

架构：`web`(nginx: 静态前端 + 反代) → `api`(FastAPI) + `mysql` + `redis`。详见 `开发部署工作流方案.md`。
