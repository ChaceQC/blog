#!/usr/bin/env bash
set -euo pipefail

# 在 Debian 服务器上执行，默认先备份 MySQL，再运行后端 Alembic 迁移。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_BACKUP="${RUN_BACKUP:-yes}"
BUILD_BACKEND="${BUILD_BACKEND:-yes}"
COMPOSE_FILES=(
  -f "${DEPLOY_DIR}/docker-compose.yml"
  -f "${DEPLOY_DIR}/docker-compose.prod.yml"
)

if [[ -n "${COMPOSE_EXTRA_FILES:-}" ]]; then
  for compose_file in ${COMPOSE_EXTRA_FILES}; do
    COMPOSE_FILES+=(-f "${compose_file}")
  done
fi

if [[ "${RUN_BACKUP}" != "no" ]]; then
  bash "${SCRIPT_DIR}/backup_mysql.sh"
fi

if [[ "${BUILD_BACKEND}" != "no" ]]; then
  docker compose "${COMPOSE_FILES[@]}" build backend
fi

docker compose "${COMPOSE_FILES[@]}" run --rm backend \
  alembic upgrade head

docker compose "${COMPOSE_FILES[@]}" run --rm backend \
  alembic current

echo "数据库迁移已完成。"
