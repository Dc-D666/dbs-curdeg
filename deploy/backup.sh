#!/usr/bin/env bash
# 数据库备份脚本（含存储过程/触发器/事件 —— 审查报告整改项）
#
# 用法（服务器上执行）：
#   bash /opt/channel/deploy/backup.sh                 # 备份到 ./backups/
#   bash /opt/channel/deploy/backup.sh /other/path    # 自定义目录
#
# 要点：
#   --single-transaction  InnoDB 一致性快照，不锁表
#   --routines            存储过程 + 函数（sp_reconcile_counters / fn_post_heat）
#   --triggers            触发器（counter_audit 对账台账 ×10）
#   --events              事件（短链清理 / 禁言解除 / 计数器对账）
#   旧版 mysqldump 漏掉以上三个参数会静默丢失全部数据库对象！
#
# 建议 crontab（每日 4:30）：
#   30 4 * * * bash /opt/channel/deploy/backup.sh >> /var/log/guild-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${1:-$(cd "$(dirname "$0")" && pwd)/backups}"
COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$BACKUP_DIR"

STAMP="$(date '+%Y%m%d_%H%M%S')"
FILE="$BACKUP_DIR/guild_backup_$STAMP.sql"

# 从部署 .env 读取 root 密码（不入库、不打印）
# shellcheck disable=SC1091
source "$COMPOSE_DIR/.env"

echo "[$(date '+%F %T')] dumping guild -> $FILE"
docker compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T mysql \
  mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
  --single-transaction --routines --triggers --events \
  --set-gtid-purged=OFF --default-character-set=utf8mb4 \
  guild > "$FILE"

# 校验：文件非空且包含关键对象（防止"假成功"备份）
SIZE=$(stat -c%s "$FILE")
if [ "$SIZE" -lt 10240 ]; then
  echo "!! 备份过小($SIZE 字节)，疑似失败" >&2
  exit 1
fi
for obj in "CREATE TABLE \`posts\`" "CREATE VIEW" "CREATE TRIGGER" "CREATE DEFINER"; do
  if ! grep -q "$obj" "$FILE"; then
    echo "!! 备份缺少对象: $obj（检查 --routines/--triggers/--events 参数）" >&2
    exit 1
  fi
done

gzip -f "$FILE"
echo "[$(date '+%F %T')] OK: $FILE.gz ($((SIZE / 1024)) KB)"

# 保留最近 14 份，其余清理
ls -1t "$BACKUP_DIR"/guild_backup_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm --
echo "[$(date '+%F %T')] cleaned old backups (keep 14)"
