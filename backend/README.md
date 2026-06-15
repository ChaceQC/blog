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
uv run python -m app.cli --help
```

本地端口、数据库连接、CORS 和上传目录都来自 `.env`，不要写死在代码里。

## 后台认证

后台认证接口位于 `/api/admin/auth`：

- `POST /login`：校验用户名和密码，签发短期 Access Token 与 Refresh Token。
- `POST /refresh`：校验并轮换 Refresh Token，重新签发令牌。
- `POST /logout`：吊销当前 Refresh Token。

密码使用 Argon2id 校验，Refresh Token 只存储 SHA-256 哈希。Token 有效期通过 `BLOG_ACCESS_TOKEN_EXPIRE_MINUTES` 和 `BLOG_REFRESH_TOKEN_EXPIRE_DAYS` 配置。

## 初始管理员

连接真实数据库并执行迁移后，使用 CLI 创建初始后台管理员：

```powershell
$env:PYTHONUTF8='1'
uv run python -m app.cli create-admin --username admin --email admin@example.com --display-name 管理员
```

省略 `--password` 时会交互式输入密码，生产环境不建议把密码写入命令历史。

## 数据库迁移

迁移文件位于 `migrations/versions`，通过 Alembic 管理。连接真实 MySQL 后，使用以下命令执行迁移：

```powershell
$env:PYTHONUTF8='1'
uv run alembic upgrade head
```

## 部署目标

生产部署环境为 Linux Debian，使用 Docker Compose、Nginx、MySQL 和私有容器网络。公网只允许 Nginx 暴露 `80/443`。
