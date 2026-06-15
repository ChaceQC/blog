# 后端工程

本目录是个人博客系统的 FastAPI 后端工程。

## 本地开发

开发环境默认为 Windows 11，终端和文件读写统一使用 UTF-8。本地开发避免使用常见端口，后端默认端口为 `18080`。

```powershell
uv sync
Copy-Item .env.example .env
uv run python main.py
uv run pytest
uv run ruff check .
$env:PYTHONUTF8='1'
uv run alembic upgrade head --sql
```

本地端口、数据库连接、CORS 和上传目录都来自 `.env`，不要写死在代码里。

## 数据库迁移

迁移文件位于 `migrations/versions`，通过 Alembic 管理。连接真实 MySQL 后，使用以下命令执行迁移：

```powershell
$env:PYTHONUTF8='1'
uv run alembic upgrade head
```

## 部署目标

生产部署环境为 Linux Debian，使用 Docker Compose、Nginx、MySQL 和私有容器网络。公网只允许 Nginx 暴露 `80/443`。
