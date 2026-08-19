#!/usr/bin/env bash
# 服务器一键更新：拉最新代码 → 重建镜像 → 重启容器
# 用法：cd /opt/channel && ./deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 拉取最新代码"
git fetch origin main
git reset --hard origin/main

echo "==> 构建并重启"
cd deploy
docker compose up -d --build

echo "==> 清理旧镜像"
docker image prune -f

echo "==> 完成"
