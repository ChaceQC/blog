#!/usr/bin/env bash
set -euo pipefail

# 在 Debian 服务器上执行，生成 gzip 压缩的 MySQL 备份。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/data/blog/backups/mysql}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${BACKUP_DIR}/blog-${TIMESTAMP}.sql.gz"
COMPOSE_FILES=(
  -f "${DEPLOY_DIR}/docker-compose.yml"
  -f "${DEPLOY_DIR}/docker-compose.prod.yml"
)

if [[ -n "${COMPOSE_EXTRA_FILES:-}" ]]; then
  for compose_file in ${COMPOSE_EXTRA_FILES}; do
    COMPOSE_FILES+=(-f "${compose_file}")
  done
fi

mkdir -p "${BACKUP_DIR}"

docker compose "${COMPOSE_FILES[@]}" \
  exec -T mysql \
  sh -c 'mysqldump -uroot -p"${MYSQL_ROOT_PASSWORD}" --single-transaction --routines --triggers "${MYSQL_DATABASE}"' \
  | gzip > "${OUTPUT_FILE}"

echo "备份已生成：${OUTPUT_FILE}"
