#!/usr/bin/env bash
set -euo pipefail

# 从 gzip 压缩备份恢复上传文件。会覆盖同名文件，但不会删除现有额外文件。
if [[ $# -ne 1 ]]; then
  echo "用法：CONFIRM_RESTORE_UPLOADS=yes restore_uploads.sh /data/blog/backups/uploads/uploads-YYYYMMDDTHHMMSSZ.tar.gz" >&2
  exit 1
fi

if [[ "${CONFIRM_RESTORE_UPLOADS:-}" != "yes" ]]; then
  echo "恢复上传文件会覆盖同名文件；如已确认目标目录和备份文件，请设置 CONFIRM_RESTORE_UPLOADS=yes 后重试。" >&2
  exit 1
fi

BACKUP_FILE="$1"
UPLOAD_ROOT="${UPLOAD_ROOT:-/data/blog/uploads}"

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "上传文件备份不存在：${BACKUP_FILE}" >&2
  exit 1
fi

while IFS= read -r entry; do
  if [[ "${entry}" == /* ||
        "${entry}" == ".." ||
        "${entry}" == ../* ||
        "${entry}" == */.. ||
        "${entry}" == */../* ]]; then
    echo "备份包包含不安全路径：${entry}" >&2
    exit 1
  fi
done < <(tar -tzf "${BACKUP_FILE}")

mkdir -p "${UPLOAD_ROOT}"
tar -C "${UPLOAD_ROOT}" -xzf "${BACKUP_FILE}"

echo "上传文件恢复完成：${BACKUP_FILE} -> ${UPLOAD_ROOT}"
