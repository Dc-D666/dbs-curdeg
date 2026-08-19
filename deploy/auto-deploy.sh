#!/usr/bin/env bash
# 服务器 cron 自动部署脚本（每 3 分钟）—— 已版本化进仓库，改进走 git 流。
#
# 逻辑：git fetch 有变化 → reset 到新提交 → 重建重启 → 健康检查通过才算成功；
#       构建失败或健康检查超时 → 自动回滚到上一提交并重建，避免线上挂着坏版本。
#
# cron 示例（root）：
#   */3 * * * * /opt/channel/deploy/auto-deploy.sh >> /var/log/auto-deploy.log 2>&1
#
# 环境变量覆盖（一般不需要）：
#   HEALTH_URL       健康检查地址，默认 https://127.0.0.1/healthz（nginx 443）
#   HEALTH_MAX_WAIT  健康检查最长等待秒数，默认 60
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_DIR/deploy/docker-compose.yml"
HEALTH_URL="${HEALTH_URL:-https://127.0.0.1/healthz}"
HEALTH_MAX_WAIT="${HEALTH_MAX_WAIT:-60}"

log() { echo "[$(date '+%F %T')] $*"; }

cd "$REPO_DIR"

# 1. 拉取并比对（无变化直接退出，cron 每 3 分钟的空跑成本约 1 秒）
git fetch origin main
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi
PREVIOUS="$LOCAL"
log "检测到新提交 $REMOTE（上一提交 $PREVIOUS），开始部署"

# 2. 切换到新提交（必须 reset，否则 compose 构建的是旧工作区 → 假成功）
git reset --hard "$REMOTE"

# 3. 部署新代码（docker layer 缓存让未变更服务秒级完成）
rollback() {
  log "回滚到 $PREVIOUS"
  if ! git reset --hard "$PREVIOUS"; then
    log "⚠️ git 回滚失败，服务器代码停留在 $REMOTE（下次 push 可恢复）"
    return 1
  fi
  docker compose -f "$COMPOSE_FILE" up -d --build || log "⚠️ 回滚后重建失败，需人工介入"
}

if ! docker compose -f "$COMPOSE_FILE" up -d --build; then
  log "构建失败，自动回滚"
  rollback
  exit 1
fi

# 4. 健康检查（-k 忽略证书域名校验：本机 127.0.0.1 访问，证书是 guild.weaxi.cn 的）
ok=0
for _ in $(seq 1 $((HEALTH_MAX_WAIT / 2))); do
  if curl -sfk "$HEALTH_URL" >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done

if [ "$ok" != "1" ]; then
  log "健康检查 ${HEALTH_MAX_WAIT}s 内未通过，自动回滚"
  rollback
  exit 1
fi

# 5. 清理旧镜像
docker image prune -f >/dev/null 2>&1 || true

log "部署成功：$REMOTE（健康检查通过）"
