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
- `GET /me`：通过 HttpOnly Access Token Cookie 或 Bearer Token 校验当前后台用户，返回用户、角色、权限和 CSRF Token。

密码使用 Argon2id 校验。浏览器会话使用 HttpOnly Cookie 保存 Access Token 和 Refresh Token，前端只持有用户信息和 CSRF Token；刷新和退出等写操作必须携带 `X-CSRF-Token`。Refresh Token 只存储 SHA-256 哈希。Token 有效期通过 `BLOG_ACCESS_TOKEN_EXPIRE_MINUTES` 和 `BLOG_REFRESH_TOKEN_EXPIRE_DAYS` 配置，Cookie 安全属性通过 `BLOG_ADMIN_COOKIE_SECURE` 和 `BLOG_ADMIN_COOKIE_SAMESITE` 配置。

MySQL 8 默认认证插件需要 `asyncmy` 配合 `cryptography` 完成认证，依赖文件中已显式保留该运行依赖。

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

## 本地 MySQL 验证

Windows 本机安装 MySQL 8 时，可以使用临时库验证真实迁移和认证流程。根目录 `auth.txt` 可保存本机 MySQL root 凭据供本地验证使用，该文件属于机密文件，已被 `.gitignore` 忽略，禁止提交。

验证建议只操作临时库，例如 `blog_codex_migration_test`：

1. 创建或重建临时库。
2. 临时设置 `BLOG_DATABASE_URL` 指向该临时库。
3. 运行 `uv run alembic upgrade head` 验证真实建表。
4. 运行 `uv run python -m app.cli create-admin ...` 验证初始管理员创建。
5. 通过服务层或接口验证登录、当前用户、刷新令牌和退出。
6. 运行 `uv run alembic downgrade base` 后删除临时库。

## 部署目标

生产部署环境为 Linux Debian，使用 Docker Compose、Nginx、MySQL 和私有容器网络。公网只允许 Nginx 暴露 `80/443`。
