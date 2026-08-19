#!/bin/sh
# api 容器入口：先执行数据库迁移，再启动服务。
# 为什么在这里迁移：服务器 auto-deploy.sh 每次 git pull 后直接 up -d --build，
# 容器启动时跑 alembic upgrade head 保证新迁移自动生效（详见 详细开发方案.md §10）。
set -e

echo "[entrypoint] 执行数据库迁移..."
alembic upgrade head

echo "[entrypoint] 启动 uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
