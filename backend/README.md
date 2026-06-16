# 后端工程

本目录是个人博客系统的 FastAPI 后端工程。

## 本地开发

开发环境默认为 Windows 11，终端和文件读写统一使用 UTF-8。本地开发避免使用常见端口，后端默认端口为 `18080`。
本地启动后端必须使用 `uv run python main.py`，不要直接调用系统 Python 或全局 Python；浏览器联调、接口联调或端到端验证完成后，应关闭本次启动的后端服务并确认 `18080` 不再由本项目进程监听。

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

- `GET /api/admin/audit-logs`：操作审计日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。
- `GET /api/admin/access-logs`：公开访问、文件下载和文章图片渲染日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。
- `GET /api/admin/login-logs`：后台登录日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。
- `GET /api/admin/security-events`：安全事件日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。

登录入口和加密协商入口已接入可配置限流，命中后返回 `429` 并写入 `security_events`。阈值通过 `BLOG_ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS`、`BLOG_ADMIN_LOGIN_RATE_LIMIT_WINDOW_SECONDS`、`BLOG_ENCRYPTION_SESSION_RATE_LIMIT_MAX_ATTEMPTS` 和 `BLOG_ENCRYPTION_SESSION_RATE_LIMIT_WINDOW_SECONDS` 配置。当前实现为单进程内存限流器，适合 M1 单进程闭环验证；生产多实例或多进程部署前需要替换为 Redis 等共享存储适配器。

## 后台内容管理

后台文章和页面管理接口已接入 `content-v1` 加密请求与响应，调用方需要先协商 `/api/admin/encryption/sessions` 并携带 `X-Encryption-Session`：

- `GET /api/admin/posts`：后台文章列表，需要 `post:read` 权限。
- `POST /api/admin/posts`：创建文章，需要 `post:write` 权限和 `X-CSRF-Token`。
- `GET /api/admin/posts/{id}`：后台文章详情，需要 `post:read` 权限。
- `PATCH /api/admin/posts/{id}`：更新文章，需要 `post:write` 权限和 `X-CSRF-Token`。
- `POST /api/admin/posts/{id}/publish`：发布文章，需要 `post:publish` 权限和 `X-CSRF-Token`。
- `POST /api/admin/posts/preview`：实时渲染文章预览，需要 `post:write` 权限和 `X-CSRF-Token`，只返回渲染后的 HTML，不写入数据库。
- `GET /api/admin/pages`、`GET /api/admin/pages/{id}`、`POST /api/admin/pages`、`PATCH /api/admin/pages/{id}`：后台页面管理，需要 `page:write` 权限，写操作需要 `X-CSRF-Token`。

创建、更新和预览请求体必须是 `content-v1` 加密信封，解密后再进行 Pydantic 字段校验。文章创建和更新可传入 `cover_file_id`；创建、更新和发布文章时会把封面文件与正文图片引用同步写入 `file_usages`。`content_html` 由 `markdown-it-py` 渲染 Markdown，启用标题、列表、强调、分隔线、表格等常用语法，`mdit-py-plugins` 保留行内与块级 LaTeX 公式节点，再由 `bleach` 统一执行 HTML sanitize。文章 Markdown 内图片应保存为 `/api/public/posts/{slug}/files/{file_id}/render` 稳定引用；公开文章详情会为实际 HTML 图片地址补上 `expires` 与 `token`，后台实时预览会改写为 `/api/admin/files/{id}/preview` 签名地址，裸访问渲染接口会被拒绝。

## 后台文件管理

后台文件管理接口已接入 `content-v1` 加密响应，调用方需要携带 `X-Encryption-Session`：

- `GET /api/admin/files`：文件列表，需要 `file:upload` 权限。
- `POST /api/admin/files`：multipart 上传，需要 `file:upload` 权限和 `X-CSRF-Token`。
- `GET /api/admin/files/{id}/temporary-url`：为公开文件生成短时访问链接，需要 `file:upload` 权限。
- `GET /api/admin/files/{id}/preview`：为后台文章预览提供短时签名图片访问，不用于公开下载。
- `DELETE /api/admin/files/{id}`：软删除文件，需要 `file:delete` 权限和 `X-CSRF-Token`。

当前本地存储驱动会将文件写入 `BLOG_UPLOAD_ROOT`，但不会挂载静态目录，也不会为新文件写入 `/uploads/...` 公开 URL。公开文件栏下载通过后台加密接口按需生成短时签名链接，再由 `/api/public/files/{id}/download?token=...` 校验后返回文件；文章正文图片渲染使用专门的 `/api/public/posts/{slug}/files/{file_id}/render?expires=...&token=...`，签名由公开文章详情或后台预览接口按场景颁发。后台文件列表的使用次数来自 `file_usages`，目前文章封面记录为 `cover`，正文图片记录为 `post_body`。私有文件不生成公开访问链接。上传大小通过 `BLOG_UPLOAD_MAX_SIZE_BYTES` 配置，当前白名单支持 JPEG、PNG、GIF、WebP 和 PDF，并校验扩展名、MIME 与文件头；删除只标记为 `deleted`，后续由清理任务处理物理文件。短时链接有效期通过 `BLOG_FILE_TEMPORARY_URL_EXPIRE_SECONDS` 配置。公开内容读取、公开文件下载、文章图片渲染和后台短时链接生成都会写入 `access_logs`。

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
