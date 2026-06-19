# 部署目录说明

本目录保存 Debian 生产部署所需的 Compose、Nginx、环境变量模板、维护脚本和 systemd timer 示例。完整部署流程见根目录 `README.md` 的“生产部署”章节；本文件只说明 `deploy/` 内各文件的职责和注意事项。

## 目录结构

```text
deploy/
  docker-compose.yml          基础服务编排
  docker-compose.prod.yml     生产端口、重启策略和资源限制覆盖
  env/                        环境变量模板
  nginx/                      Nginx 镜像、主配置和站点模板
  scripts/                    MySQL 备份、恢复和证书续期脚本
  systemd/                    后台维护任务 service/timer 示例
```

## 环境变量模板

首次部署时复制模板并填写真实值：

```bash
cp deploy/env/backend.env.example deploy/env/backend.env
cp deploy/env/mysql.env.example deploy/env/mysql.env
cp deploy/env/nginx.env.example deploy/env/nginx.env
```

- `backend.env`：后端应用配置，包括数据库连接、密钥、公开域名、CORS、Trusted Host、Cookie、安全限流、上传目录和 Redis。
- `mysql.env`：MySQL root 密码、业务库、业务账号和密码。
- `nginx.env`：Nginx 模板渲染所需的域名和容器内证书路径。

真实 `*.env`、证书、私钥、备份文件和上传文件不得提交到 Git。

## Compose 文件

生产启动命令统一使用基础文件叠加生产覆盖文件：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

提交前或部署前可展开检查配置：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config --quiet
```

公网只应暴露 Nginx 的 `80/443`。MySQL、Redis 和后端应用端口应只在 Docker 网络内访问。

`deploy/docker-compose.local.yml` 是服务器本地覆盖文件，已被 `.gitignore` 忽略；如果需要同时放证书挂载和后端端口绑定，请编辑合并同一个文件，不要互相覆盖。

如果使用宿主机 Nginx，而不是 Compose 内置 Nginx 服务，启动后端/MySQL/Redis 时只指定这些服务。若宿主机需要通过 `127.0.0.1:18080` 访问后端容器，请在 `deploy/docker-compose.local.yml` 中加入：

```yaml
services:
  backend:
    ports:
      - "127.0.0.1:18080:8000"
```

此时后端容器看到的连接来源常是 Docker 网关地址，例如 `172.23.0.1`。为了让访问日志、登录日志和限流使用真实访客 IP，`deploy/env/backend.env` 的 `BLOG_TRUSTED_PROXY_HOSTS` 应包含该网关 IP 或 Docker bridge CIDR，例如：

```dotenv
BLOG_TRUSTED_PROXY_HOSTS=["172.16.0.0/12"]
```

宿主机 Nginx 的站点配置也必须向后端传递代理头：

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

启动命令：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml up -d --build backend mysql redis
```

MySQL 和 Redis 仍留在 Docker 内网。若仍要从 Nginx 镜像复制 React 静态文件到宿主机站点目录，需要单独构建镜像：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml build nginx
```

## Nginx

`deploy/nginx/templates/blog.conf.template` 是站点模板，负责：

- 提供 React 静态资源。
- 反向代理 `/api/` 到后端。
- 精确反代 `/rss.xml`、`/sitemap.xml` 和 `/robots.txt`，避免被 SPA 的 `index.html` 兜底吞掉。
- 设置上传体积限制、基础安全响应头和代理头。当前模板使用 `client_max_body_size 20m`，后端生产环境变量应同步为 `BLOG_UPLOAD_MAX_SIZE_BYTES=20971520`。

上传文件目录不挂载到 Nginx，也不提供 `/uploads/` 静态访问；公开文件、文章图片和后台预览均由后端签名接口授权。宿主机 Nginx 部署时也不要手动添加 `/uploads/` alias。

后端生产响应也会设置 HSTS 与 Content Security Policy，Nginx 的同类响应头保留为公网入口兜底；部署前仍应确认公网只暴露 Nginx `80/443`，后端、MySQL、Redis 不映射到宿主公网端口。

证书路径由 `deploy/env/nginx.env` 中的 `BLOG_SSL_CERTIFICATE` 和 `BLOG_SSL_CERTIFICATE_KEY` 控制，填写的是 Nginx 容器内路径。基础 Compose 文件默认挂载 `deploy/certs/letsencrypt` 到 `/etc/letsencrypt`；如果使用宿主机已有证书，例如 `/etc/nginx/ssl/blog.pem` 和 `/etc/nginx/ssl/blog.key`，需要在 `deploy/docker-compose.local.yml` 中加入证书目录挂载：

```yaml
services:
  nginx:
    volumes:
      - /etc/nginx/ssl:/etc/nginx/ssl:ro
```

启动时叠加该文件：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml up -d --build
```

生产 `BLOG_PUBLIC_BASE_URL` 必须与 Nginx 对外 HTTPS 域名一致，否则 RSS、sitemap、robots.txt 和签名链接会生成错误的绝对地址。

## 维护脚本

`deploy/scripts/` 当前包含：

- `backup_mysql.sh`：备份 MySQL。
- `upgrade_backend_db.sh`：默认先备份 MySQL、构建 backend 镜像，再用一次性后端容器执行 Alembic 数据库迁移。
- `restore_mysql.sh`：恢复 MySQL。
- `backup_uploads.sh`：备份上传文件目录，默认读取 `/data/blog/uploads` 并写入 `/data/blog/backups/uploads`。
- `restore_uploads.sh`：恢复上传文件目录，会覆盖同名文件但不会删除现有额外文件；执行前必须设置 `CONFIRM_RESTORE_UPLOADS=yes`。
- `renew_cert.sh`：证书续期示例。

备份至少应覆盖 MySQL、上传文件目录、生产环境变量、证书和部署版本信息。备份文件应加密保存到服务器外部位置，并定期做恢复演练。

发布包含数据库迁移的新版本后执行：

```bash
bash deploy/scripts/upgrade_backend_db.sh
```

如已通过其他方式完成备份，可跳过脚本内置备份：

```bash
RUN_BACKUP=no bash deploy/scripts/upgrade_backend_db.sh
```

如已确认 backend 镜像包含最新迁移文件，也可跳过构建：

```bash
BUILD_BACKEND=no bash deploy/scripts/upgrade_backend_db.sh
```

如果生产使用宿主机 Nginx 本地覆盖文件，维护脚本可通过 `COMPOSE_EXTRA_FILES`
追加同一份覆盖配置，MySQL 备份、恢复和迁移脚本都会复用：

```bash
COMPOSE_EXTRA_FILES=deploy/docker-compose.local.yml \
  bash deploy/scripts/upgrade_backend_db.sh
```

## systemd Timer

`deploy/systemd/` 提供宿主机调度示例，默认假设项目部署在 `/opt/blog`。如果实际路径不同，先修改各 `.service` 的 `WorkingDirectory`。

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blog-backup-mysql.timer
sudo systemctl enable --now blog-backup-uploads.timer
sudo systemctl enable --now blog-cleanup-encryption-sessions.timer
sudo systemctl enable --now blog-cleanup-deleted-files.timer
sudo systemctl enable --now blog-cleanup-logs.timer
sudo systemctl enable --now blog-scan-orphan-files.timer
sudo systemctl enable --now blog-check-friend-links.timer
systemctl list-timers 'blog-*'
```

任务说明：

- `blog-backup-mysql.timer`：每天备份 MySQL。
- `blog-backup-uploads.timer`：每天备份上传文件目录。
- `blog-cleanup-encryption-sessions.timer`：每小时清理过期加密会话。
- `blog-cleanup-deleted-files.timer`：每天清理超过保留期、无引用且路径安全的软删除文件。
- `blog-cleanup-logs.timer`：每天按保留天数清理数据库日志，默认访问日志 30 天，审计/登录/安全事件 180 天。
- `blog-scan-orphan-files.timer`：每周 dry-run 扫描孤儿文件，只输出汇总和示例。
- `blog-check-friend-links.timer`：每天检查已通过友链的 HTTP 状态，不自动改变人工审核状态。

孤儿文件真实删除必须人工确认 dry-run 输出后再执行：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-orphan-files --limit 1000 --delete
```
