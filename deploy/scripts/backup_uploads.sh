#!/usr/bin/env bash
set -euo pipefail

# 在 Debian 服务器上执行，生成 gzip 压缩的上传文件目录备份。
UPLOAD_ROOT="${UPLOAD_ROOT:-/data/blog/uploads}"
BACKUP_DIR="${BACKUP_DIR:-/data/blog/backups/uploads}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${BACKUP_DIR}/uploads-${TIMESTAMP}.tar.gz"

if [[ ! -d "${UPLOAD_ROOT}" ]]; then
  echo "上传目录不存在：${UPLOAD_ROOT}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

tar -C "${UPLOAD_ROOT}" -czf "${OUTPUT_FILE}" .

echo "上传文件备份已生成：${OUTPUT_FILE}"
