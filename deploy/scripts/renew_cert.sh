#!/usr/bin/env bash
set -euo pipefail

# 使用 webroot 方式申请或续期 Let's Encrypt 证书。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NGINX_ENV="${DEPLOY_DIR}/env/nginx.env"

if [[ ! -f "${NGINX_ENV}" ]]; then
  echo "缺少环境文件：${NGINX_ENV}" >&2
  exit 1
fi

set -a
source "${NGINX_ENV}"
set +a

docker compose \
  -f "${DEPLOY_DIR}/docker-compose.yml" \
  -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
  run --rm certbot \
  certonly --webroot \
  -w /var/www/certbot \
  -d "${BLOG_DOMAIN}" \
  --email "${LETSENCRYPT_EMAIL}" \
  --agree-tos \
  --no-eff-email

docker compose \
  -f "${DEPLOY_DIR}/docker-compose.yml" \
  -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
  exec nginx nginx -s reload

echo "证书已申请或续期：${BLOG_DOMAIN}"
