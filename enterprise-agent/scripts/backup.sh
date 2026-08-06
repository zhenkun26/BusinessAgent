#!/bin/bash
# 每日备份脚本:PostgreSQL 逻辑备份 + Milvus 全量(etcd 元数据 + MinIO 对象 + milvus 本地卷)
# 对应 deploy/DEPLOY.md 5.1;load-test-and-dr-drill change 将其从文档示例落成可执行脚本,
# 并按首次恢复演练结论(ISSUES I-12)补齐 MinIO/milvus 数据卷——缺这两样 Milvus 集合不可恢复。
#
# 用法:
#   scripts/backup.sh                     # 默认:docker-compose.yml,产出到 ./backups/
#   BACKUP_DIR=/data/backups RETAIN_DAYS=14 scripts/backup.sh
#
# 产出:
#   backups/pg_<YYYYMMDD_HHMMSS>.sql.gz      PG 逻辑备份
#   backups/etcd_<YYYYMMDD_HHMMSS>.db        etcd snapshot(Milvus 元数据)
#   backups/minio_<YYYYMMDD_HHMMSS>.tar.gz   MinIO 对象存储整卷(Milvus 向量数据本体)
#   backups/milvus_<YYYYMMDD_HHMMSS>.tar.gz  milvus 本地卷整卷(rocksmq 等)
#
# 注意:整卷 tar 是在运行中系统上的近一致快照(非原子);如需严格一致,
#      备份前 stop milvus-standalone(可设 STOP_MILVUS=1,会短暂中断检索)。
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP_DIR=${BACKUP_DIR:-backups}
COMPOSE_FILES=${COMPOSE_FILES:--f docker-compose.yml}
COMPOSE_PROJECT=${COMPOSE_PROJECT:-enterprise-agent}
RETAIN_DAYS=${RETAIN_DAYS:-7}
PG_USER=${PG_USER:-agent}
PG_DB=${PG_DB:-enterprise_agent}
STOP_MILVUS=${STOP_MILVUS:-0}
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

compose() { docker compose -p "$COMPOSE_PROJECT" $COMPOSE_FILES "$@"; }

# 1. PostgreSQL 逻辑备份
compose exec -T postgres pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$BACKUP_DIR/pg_$DATE.sql.gz"

# 2. Milvus 元数据(etcd 备份)
compose exec -T etcd etcdctl snapshot save /tmp/etcd_backup.db
compose cp etcd:/tmp/etcd_backup.db "$BACKUP_DIR/etcd_$DATE.db"

# 3. Milvus 数据本体:MinIO 对象存储 + milvus 本地卷(整卷 tar,近一致快照)
if [ "$STOP_MILVUS" = "1" ]; then
  compose stop milvus-standalone
fi
docker run --rm -v "${COMPOSE_PROJECT}_minio_data:/data:ro" -v "$PWD/$BACKUP_DIR:/b" alpine \
  tar czf "/b/minio_$DATE.tar.gz" -C /data .
docker run --rm -v "${COMPOSE_PROJECT}_milvus_data:/data:ro" -v "$PWD/$BACKUP_DIR:/b" alpine \
  tar czf "/b/milvus_$DATE.tar.gz" -C /data .
if [ "$STOP_MILVUS" = "1" ]; then
  compose start milvus-standalone
fi

# 4. 清理过期备份
find "$BACKUP_DIR" -name "*.gz" -mtime +"$RETAIN_DAYS" -delete
find "$BACKUP_DIR" -name "*.db" -mtime +"$RETAIN_DAYS" -delete

echo "[$DATE] 备份完成: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"/*_"$DATE".*
