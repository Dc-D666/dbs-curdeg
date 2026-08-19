#!/usr/bin/env bash
# 服务器一键更新：拉最新代码 → 选择性重建 → 重启容器
# 用法（cd /opt/channel 后）：
#   ./deploy/deploy.sh          全量构建并重启（默认）
#   ./deploy/deploy.sh api      只构建/重启后端（仅前端改动时用，省一半构建时间）
#   ./deploy/deploy.sh web      只构建/重启前端（仅后端改动时用）
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"

echo "==> 拉取最新代码"
git fetch origin main
git reset --hard origin/main

echo "==> 构建并重启（目标: ${TARGET:-全部}）"
cd deploy
if [ -n "$TARGET" ]; then
  docker compose up -d --build "$TARGET"
else
  docker compose up -d --build
fi

echo "==> 清理旧镜像"
docker image prune -f

echo "==> 完成"
