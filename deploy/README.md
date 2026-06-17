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
- `nginx.env`：Nginx 模板渲染所需的域名、证书路径和代理目标。

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

## Nginx

`deploy/nginx/templates/blog.conf.template` 是站点模板，负责：

- 提供 React 静态资源。
- 反向代理 `/api/` 到后端。
- 精确反代 `/rss.xml`、`/sitemap.xml` 和 `/robots.txt`，避免被 SPA 的 `index.html` 兜底吞掉。
- 设置上传体积限制、基础安全响应头和代理头。

后端生产响应也会设置 HSTS 与 Content Security Policy，Nginx 的同类响应头保留为公网入口兜底；部署前仍应确认公网只暴露 Nginx `80/443`，后端、MySQL、Redis 不映射到宿主公网端口。

生产 `BLOG_PUBLIC_BASE_URL` 必须与 Nginx 对外 HTTPS 域名一致，否则 RSS、sitemap、robots.txt 和签名链接会生成错误的绝对地址。

## 维护脚本

`deploy/scripts/` 当前包含：

- `backup_mysql.sh`：备份 MySQL。
- `restore_mysql.sh`：恢复 MySQL。
- `renew_cert.sh`：证书续期示例。

备份至少应覆盖 MySQL、上传文件目录、生产环境变量、证书和部署版本信息。备份文件应加密保存到服务器外部位置，并定期做恢复演练。

## systemd Timer

`deploy/systemd/` 提供宿主机调度示例，默认假设项目部署在 `/opt/blog`。如果实际路径不同，先修改各 `.service` 的 `WorkingDirectory`。

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blog-cleanup-encryption-sessions.timer
sudo systemctl enable --now blog-cleanup-deleted-files.timer
sudo systemctl enable --now blog-scan-orphan-files.timer
sudo systemctl enable --now blog-check-friend-links.timer
systemctl list-timers 'blog-*'
```

任务说明：

- `blog-cleanup-encryption-sessions.timer`：每小时清理过期加密会话。
- `blog-cleanup-deleted-files.timer`：每天清理超过保留期、无引用且路径安全的软删除文件。
- `blog-scan-orphan-files.timer`：每周 dry-run 扫描孤儿文件，只输出汇总和示例。
- `blog-check-friend-links.timer`：每天检查已通过友链的 HTTP 状态，不自动改变人工审核状态。

孤儿文件真实删除必须人工确认 dry-run 输出后再执行：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-orphan-files --limit 1000 --delete
```
