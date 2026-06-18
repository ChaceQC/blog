#!/usr/bin/env bash
set -euo pipefail

# 从 gzip 压缩备份恢复 MySQL。执行前请确认目标数据库可以被覆盖。
if [[ $# -ne 1 ]]; then
  echo "用法：restore_mysql.sh /data/blog/backups/mysql/blog-YYYYMMDDTHHMMSSZ.sql.gz" >&2
  exit 1
fi

BACKUP_FILE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILES=(
  -f "${DEPLOY_DIR}/docker-compose.yml"
  -f "${DEPLOY_DIR}/docker-compose.prod.yml"
)

if [[ -n "${COMPOSE_EXTRA_FILES:-}" ]]; then
  for compose_file in ${COMPOSE_EXTRA_FILES}; do
    COMPOSE_FILES+=(-f "${compose_file}")
  done
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "备份文件不存在：${BACKUP_FILE}" >&2
  exit 1
fi

gzip -dc "${BACKUP_FILE}" | docker compose "${COMPOSE_FILES[@]}" \
  exec -T mysql \
  sh -c 'mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}"'

echo "恢复完成：${BACKUP_FILE}"
