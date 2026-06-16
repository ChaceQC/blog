# 部署说明

本目录用于 Linux Debian 生产部署。开发机默认为 Windows 11，生产环境只通过 Nginx 暴露 `80/443`，后端、MySQL、Redis 均保留在 Docker 私有网络内。

## 文件结构

- `docker-compose.yml`：基础服务编排。
- `docker-compose.prod.yml`：生产端口、重启策略和资源限制覆盖。
- `nginx/`：Nginx 镜像、主配置和站点模板。
- `env/*.env.example`：环境变量模板，复制为同名 `.env` 后再修改。
- `scripts/`：MySQL 备份、恢复和证书续期脚本。
- `systemd/`：后台维护任务的 service/timer 示例。

## 首次部署

```bash
cp deploy/env/backend.env.example deploy/env/backend.env
cp deploy/env/mysql.env.example deploy/env/mysql.env
cp deploy/env/nginx.env.example deploy/env/nginx.env
```

修改真实域名、数据库密码和 `BLOG_SECRET_KEY` 后启动：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

## 后台维护任务

后台维护任务通过 systemd timer 在宿主机调度，再进入后端容器执行 CLI，不额外开放 HTTP 入口。示例默认假设项目部署在 `/opt/blog`，如果使用其他目录，先修改 `deploy/systemd/*.service` 中的 `WorkingDirectory`。

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blog-cleanup-encryption-sessions.timer
sudo systemctl enable --now blog-cleanup-deleted-files.timer
sudo systemctl enable --now blog-scan-orphan-files.timer
```

- `blog-cleanup-encryption-sessions.timer`：每小时清理过期加密会话。
- `blog-cleanup-deleted-files.timer`：每天清理超过 7 天、无引用且路径安全的软删除文件。
- `blog-scan-orphan-files.timer`：每周 dry-run 扫描孤儿文件，只输出汇总和示例，不自动删除。

查看任务：

```bash
systemctl list-timers 'blog-*'
journalctl -u blog-cleanup-deleted-files.service
```

孤儿文件真实删除需要人工确认 dry-run 输出后手动进入后端容器执行：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-orphan-files --limit 1000 --delete
```

## 安全边界

- 公网只开放 Nginx 的 `80/443`。
- MySQL `3306`、Redis `6379` 和后端 `8000` 不映射到宿主机公网端口。
- 上传文件真实路径和对象 key 使用英文，中文文件名作为展示字段单独保存。
- `deploy/env/*.env`、证书和备份文件不得提交到 Git。
