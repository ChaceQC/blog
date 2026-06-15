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
uv run alembic downgrade 20260615_0002:20260615_0001 --sql
uv run python -m app.cli --help
```

本地端口、数据库连接、CORS 和上传目录都来自 `.env`，不要写死在代码里。

## 后台认证

后台认证接口位于 `/api/admin/auth`：

- `POST /login`：校验用户名和密码，签发短期 Access Token 与 Refresh Token，并返回 `sensitive-v1` 加密信封。
- `POST /refresh`：校验并轮换 Refresh Token，重新签发令牌，并返回 `sensitive-v1` 加密信封。
- `POST /logout`：吊销当前 Refresh Token。
- `GET /me`：通过 HttpOnly Access Token Cookie 或 Bearer Token 校验当前后台用户，并返回包含用户、角色、权限和 CSRF Token 的 `sensitive-v1` 加密信封。

密码使用 Argon2id 校验。浏览器会话使用 HttpOnly Cookie 保存 Access Token 和 Refresh Token，前端只持有用户信息和 CSRF Token；刷新和退出等写操作必须携带 `X-CSRF-Token`。登录、刷新和当前用户接口必须先通过 `/api/admin/encryption/sessions` 协商 P-256 ECDH 短期加密会话，并在请求中携带 `X-Encryption-Session`，旧的明文 JSON 响应形态已移除。协商会话保存到 `encryption_sessions` 数据表。Refresh Token 只存储 SHA-256 哈希。Token 有效期通过 `BLOG_ACCESS_TOKEN_EXPIRE_MINUTES` 和 `BLOG_REFRESH_TOKEN_EXPIRE_DAYS` 配置，Cookie 安全属性通过 `BLOG_ADMIN_COOKIE_SECURE` 和 `BLOG_ADMIN_COOKIE_SAMESITE` 配置。

MySQL 8 默认认证插件需要 `asyncmy` 配合 `cryptography` 完成认证，依赖文件中已显式保留该运行依赖。

## 安全日志与限流

后台只读日志接口：

- `GET /api/admin/audit-logs`：操作审计日志，需要 `audit_log:read` 权限。
- `GET /api/admin/login-logs`：后台登录日志，需要 `audit_log:read` 权限。
- `GET /api/admin/security-events`：安全事件日志，需要 `audit_log:read` 权限。

登录入口和加密协商入口已接入可配置限流，命中后返回 `429` 并写入 `security_events`。阈值通过 `BLOG_ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS`、`BLOG_ADMIN_LOGIN_RATE_LIMIT_WINDOW_SECONDS`、`BLOG_ENCRYPTION_SESSION_RATE_LIMIT_MAX_ATTEMPTS` 和 `BLOG_ENCRYPTION_SESSION_RATE_LIMIT_WINDOW_SECONDS` 配置。当前实现为单进程内存限流器，适合 M1 单进程闭环验证；生产多实例或多进程部署前需要替换为 Redis 等共享存储适配器。

## 后台内容管理

后台文章和页面管理接口已接入 `content-v1` 加密响应，调用方需要先协商 `/api/admin/encryption/sessions` 并携带 `X-Encryption-Session`：

- `GET /api/admin/posts`：后台文章列表，需要 `post:read` 权限。
- `POST /api/admin/posts`：创建文章，需要 `post:write` 权限和 `X-CSRF-Token`。
- `GET /api/admin/posts/{id}`：后台文章详情，需要 `post:read` 权限。
- `PATCH /api/admin/posts/{id}`：更新文章，需要 `post:write` 权限和 `X-CSRF-Token`。
- `POST /api/admin/posts/{id}/publish`：发布文章，需要 `post:publish` 权限和 `X-CSRF-Token`。
- `GET /api/admin/pages`、`GET /api/admin/pages/{id}`、`POST /api/admin/pages`、`PATCH /api/admin/pages/{id}`：后台页面管理，需要 `page:write` 权限，写操作需要 `X-CSRF-Token`。

当前创建和更新请求仍使用 HTTPS 下的普通 JSON，后续需要补充 `content-v1` 请求解密。`content_html` 由临时安全渲染器生成，只做 HTML 转义和段落包裹；完整 Markdown、LaTeX 和 HTML sanitize 策略仍需在后续文章编辑闭环中替换为正式渲染策略。

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
5. 通过服务层或接口验证加密协商、登录、当前用户、刷新令牌和退出。
6. 运行 `uv run alembic downgrade base` 后删除临时库。

## 部署目标

生产部署环境为 Linux Debian，使用 Docker Compose、Nginx、MySQL 和私有容器网络。公网只允许 Nginx 暴露 `80/443`。
