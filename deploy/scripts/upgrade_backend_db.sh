#!/usr/bin/env bash
set -euo pipefail

# 在 Debian 服务器上执行，默认先备份 MySQL，再运行后端 Alembic 迁移。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
RUN_BACKUP="${RUN_BACKUP:-yes}"
BUILD_BACKEND="${BUILD_BACKEND:-yes}"
DEPLOY_STARTED_SECONDS="${SECONDS}"
COMPOSE_FILES=(
  -f "${DEPLOY_DIR}/docker-compose.yml"
  -f "${DEPLOY_DIR}/docker-compose.prod.yml"
)

if [[ -n "${COMPOSE_EXTRA_FILES:-}" ]]; then
  for compose_file in ${COMPOSE_EXTRA_FILES}; do
    COMPOSE_FILES+=(-f "${compose_file}")
  done
fi

report_deployment_telemetry() {
  local exit_status="$1"
  local status="ok"
  local git_sha=""
  local duration_seconds="$((SECONDS - DEPLOY_STARTED_SECONDS))"

  if [[ "${exit_status}" -ne 0 ]]; then
    status="error"
  fi
  git_sha="$(git -C "${REPO_DIR}" rev-parse --short=12 HEAD 2>/dev/null || true)"

  local telemetry_args=(
    python -m app.cli record-deployment-finished
    --status "${status}"
    --duration-seconds "${duration_seconds}"
  )
  if [[ -n "${git_sha}" ]]; then
    telemetry_args+=(--git-sha "${git_sha}")
  fi

  set +e
  docker compose "${COMPOSE_FILES[@]}" run --rm backend \
    "${telemetry_args[@]}" >/dev/null
  if [[ "$?" -ne 0 ]]; then
    echo "部署完成遥测事件上报失败，已忽略。"
  fi
  set -e
}

on_exit() {
  local exit_status="$?"
  report_deployment_telemetry "${exit_status}"
  exit "${exit_status}"
}

trap on_exit EXIT

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
