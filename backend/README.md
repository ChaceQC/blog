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
uv run python -m app.cli cleanup-encryption-sessions
uv run python -m app.cli cleanup-deleted-files --older-than-days 7 --limit 100
uv run python -m app.cli cleanup-orphan-files --limit 1000
uv run python -m app.cli check-friend-links --limit 100 --timeout-seconds 5
$env:BLOG_TEST_REDIS_URL='redis://127.0.0.1:6379/15'
uv run pytest tests/test_rate_limit_redis_integration.py
$env:BLOG_VERIFY_ADMIN_USERNAME='admin'
$env:BLOG_VERIFY_ADMIN_PASSWORD='你的本地后台管理员密码'
uv run python scripts/verify_runtime_publish_flow.py
```

本地端口、数据库连接、CORS 和上传目录都来自 `.env`，不要写死在代码里。

## 后台认证

后台认证接口位于 `/api/admin/auth`：

- `POST /login`：校验用户名和密码，签发短期 Access Token 与 Refresh Token，并返回 `sensitive-v1` 加密信封。
- `POST /refresh`：校验并轮换 Refresh Token，重新签发令牌，并返回 `sensitive-v1` 加密信封。
- `POST /logout`：吊销当前 Refresh Token。
- `GET /me`：通过 HttpOnly Access Token Cookie 或 Bearer Token 校验当前后台用户，并返回包含用户、角色、权限和 CSRF Token 的 `sensitive-v1` 加密信封。

密码使用 Argon2id 校验。浏览器会话使用 HttpOnly Cookie 保存 Access Token 和 Refresh Token，前端只持有用户信息和 CSRF Token；刷新和退出等写操作必须携带 `X-CSRF-Token`。登录、刷新和当前用户接口必须先通过 `/api/admin/encryption/sessions` 协商 P-256 ECDH 短期加密会话，并在请求中携带 `X-Encryption-Session`，旧的明文 JSON 响应形态已移除。协商会话保存到 `encryption_sessions` 数据表；前端会用协商出的 shared secret、`session_id`、scope 和过期时间生成可逆稳定 `esid` Cookie，后端根据 `X-Encryption-Session` 查表取得 `key_material`，逆运算并校验 `esid` 的 HMAC、session、scope 和过期时间。HTTP 请求还必须携带通过 `/api/{scope}/encryption/salts` WSS 获取的一次性 `X-Encryption-Esid-Salt`，后端原子消费通过后才会继续处理，避免固定 Cookie 独立放行或并发请求互相覆盖。`Login Capsule v2`、加密请求体和加密响应体不再使用固定 HKDF salt，分别通过 WSS 获取一次性 salt lease；WSS 帧也会用 ECDH shared secret 派生的 AES-GCM 包裹密钥加密，并复用同一加密帧格式传输应用层 `ping` / `pong` 心跳。HTTP 请求需要携带 `X-Encryption-Esid-Salt` 和 `X-Encryption-Response-Salt`，加密请求/登录 capsule 体还需要携带 `salt_id`。Refresh Token 只存储 SHA-256 哈希。Token 有效期通过 `BLOG_ACCESS_TOKEN_EXPIRE_MINUTES` 和 `BLOG_REFRESH_TOKEN_EXPIRE_DAYS` 配置，Cookie 安全属性通过 `BLOG_ADMIN_COOKIE_SECURE` 和 `BLOG_ADMIN_COOKIE_SAMESITE` 配置。

MySQL 8 默认认证插件需要异步 MySQL 驱动配合 `cryptography` 完成认证，当前运行依赖使用 `aiomysql`。

## 安全日志与限流

后端会为所有响应设置 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: strict-origin-when-cross-origin` 和禁用摄像头、麦克风、地理位置的 `Permissions-Policy`。生产环境还会设置 `Strict-Transport-Security` 与 Content Security Policy；本地开发环境不设置 CSP，避免影响 FastAPI `/docs` 调试页。

后台只读日志接口：

- `GET /api/admin/audit-logs`：操作审计日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。
- `GET /api/admin/access-logs`：公开访问、文件下载和文章图片渲染日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。
- `GET /api/admin/login-logs`：后台登录日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。
- `GET /api/admin/security-events`：安全事件日志，需要 `audit_log:read` 权限和 `sensitive-v1` 加密会话。

后台文章、页面、文件、友链、导航和设置的关键写操作会写入 `audit_logs`，记录操作者、动作、实体、IP、UA 和最小变更摘要；正文、标题、slug、URL、文件名、MIME、密钥、Token 和完整设置值不写入审计日志。读取历史审计日志时也会过滤不在 allowlist 内的旧 payload 字段。

登录入口、后台/公开加密协商入口和公开友链申请入口已接入可配置限流，命中后返回 `429` 并写入 `security_events`。阈值通过 `BLOG_ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS`、`BLOG_ADMIN_LOGIN_RATE_LIMIT_WINDOW_SECONDS`、`BLOG_ENCRYPTION_SESSION_RATE_LIMIT_MAX_ATTEMPTS`、`BLOG_ENCRYPTION_SESSION_RATE_LIMIT_WINDOW_SECONDS`、`BLOG_ADMIN_ENCRYPTION_SESSION_ACTIVE_LIMIT_PER_IP`、`BLOG_PUBLIC_ENCRYPTION_SESSION_ACTIVE_LIMIT_PER_IP`、`BLOG_FRIEND_LINK_APPLICATION_RATE_LIMIT_MAX_ATTEMPTS` 和 `BLOG_FRIEND_LINK_APPLICATION_RATE_LIMIT_WINDOW_SECONDS` 配置。公开友链申请还会规范化 URL，拒绝与现有 `pending/healthy` 友链重复的 URL，并限制全站待审数量和同域待审数量，减少绕过 IP 限流后的待审核堆积。后台和公开加密会话都会在 `encryption_sessions.client_ip` 保存短期客户端 IP，用于限制单 IP 活跃 session 数量。`client_ip()` 只在直接连接来源属于 `BLOG_TRUSTED_PROXY_HOSTS` 配置的 IP 或 CIDR 时信任 `X-Forwarded-For` / `X-Real-IP`；后端被直连时会使用连接 IP，避免伪造代理头绕过限流或污染日志。生产后端容器通过 `python -m app.server` 启动，并把同一份 `BLOG_TRUSTED_PROXY_HOSTS` 传给 Uvicorn，所以终端里的运行访问日志也会按可信代理头显示真实访客 IP，并带有时间戳；时间戳按容器内 `TZ`/`tzdata` 显示，镜像默认启用 UTF-8。限流后端通过 `BLOG_RATE_LIMIT_BACKEND` 配置，本地开发可使用 `memory`，生产必须使用 `redis` 和 `BLOG_REDIS_URL=redis://redis:6379/0`，因为一次性动态 salt lease 需要跨 worker/容器共享并原子消费。Redis 限流适配器使用 sorted set 与 Lua 脚本保证单次命中检查原子性；salt lease 使用 Redis key + Lua `GET`/`DEL` 原子消费，防止重放。真实 Redis 集成测试默认跳过，设置 `BLOG_TEST_REDIS_URL` 后会验证后台登录和加密协商入口的 `429`、`Retry-After` 与安全事件记录。

成功 `GET/HEAD` 访问默认通过 `BLOG_ACCESS_LOG_DEDUPE_SECONDS=60` 做短时去重，覆盖公开内容、公开文件、文章图片、缩略图、RSS、sitemap、robots、后台短时链接和后台下载等访问：同一 IP 在窗口内重复访问同一 path 只写入第一条 `access_logs`，不把 query 参数、临时 token 或签名参数纳入去重 key，也不把列表数量、slug、文件名或 MIME 等实体摘要写入 `detail_json`。生产环境配置 `BLOG_RATE_LIMIT_BACKEND=redis` 和 `BLOG_REDIS_URL` 时会用 Redis `SET NX EX` 共享去重，Redis 不可用或本地开发时回落到进程内缓存；公开友链申请、写操作和所有 4xx/5xx 错误仍逐条记录。公开 `content-v1` 加密 GET 会在进入业务查询前校验 public scope 加密会话和 `esid` Cookie，缺少或无效 `X-Encryption-Session` / `esid` 会直接返回 400，不再先触发列表查询、详情查询或总数统计。

## 后台维护任务

后台维护任务放在 `app/tasks`，供 CLI、cron 或 systemd timer 调用，不通过公开 HTTP 入口触发。当前已提供过期应用层加密会话清理任务、软删除文件物理清理任务、本地孤儿文件扫描清理任务、友链状态检查任务和日志保留清理任务：

```powershell
$env:PYTHONUTF8='1'
uv run python -m app.cli cleanup-encryption-sessions
uv run python -m app.cli cleanup-deleted-files --older-than-days 7 --limit 100
uv run python -m app.cli cleanup-orphan-files --limit 1000
uv run python -m app.cli cleanup-orphan-files --limit 1000 --delete
uv run python -m app.cli check-friend-links --limit 100 --timeout-seconds 5
uv run python -m app.cli cleanup-logs --access-days 30 --audit-days 180 --login-days 180 --security-days 180 --limit 5000
```

`cleanup-encryption-sessions` 会删除 `encryption_sessions` 中已过期的会话记录，并输出清理数量。`cleanup-deleted-files` 只清理已软删除、超过保留天数、没有 `file_usages` 引用且 object key 解析后仍位于 `BLOG_UPLOAD_ROOT` 内的本地文件；物理文件缺失时会清理对应数据库软删记录，路径不安全或仍有引用时会跳过。默认保留 7 天，单次最多扫描 100 条。`cleanup-orphan-files` 扫描 `BLOG_UPLOAD_ROOT` 下 `public` 与 `private` 目录中的本地文件，找出没有 active/deleted 数据库记录的孤儿文件；默认只 dry-run 汇总并展示示例，只有显式传入 `--delete` 才会删除，单次默认最多扫描 1000 个本地文件。`check-friend-links` 会检查已通过友链的 HTTP 状态，写入 `last_checked_at` 和 `last_status_code`；检查器只允许 `http/https`，请求前解析域名并拒绝 localhost、内网、链路本地、metadata 等非公网地址，重定向目标也会重新校验；访问失败记录为 `0`，不会自动把人工审核状态改成拒绝。`cleanup-logs` 按 `created_at` 清理历史 `access_logs`、`audit_logs`、`login_logs` 和 `security_events`，默认访问日志保留 30 天，审计/登录/安全事件保留 180 天，每张表单次最多删除 5000 条；某类天数传 `0` 会跳过该表。生产部署可使用 `deploy/systemd` 中的 timer 示例：加密会话每小时清理、软删除文件每天清理、日志每天清理、孤儿文件每周 dry-run 扫描、友链状态每天检查。后续 sitemap 刷新也应沿用同一类维护任务入口。

## 后台内容管理

后台文章和页面管理接口已接入 `content-v1` 加密请求与响应，调用方需要先协商 `/api/admin/encryption/sessions` 并携带 `X-Encryption-Session`：

- `GET /api/admin/posts`：后台文章列表，需要 `post:read` 权限。
- `POST /api/admin/posts`：创建文章，需要 `post:write` 权限和 `X-CSRF-Token`。
- `GET /api/admin/posts/{id}`：后台文章详情，需要 `post:read` 权限。
- `PATCH /api/admin/posts/{id}`：更新文章，需要 `post:write` 权限和 `X-CSRF-Token`。
- `POST /api/admin/posts/{id}/publish`：发布文章，需要 `post:publish` 权限和 `X-CSRF-Token`。
- `POST /api/admin/posts/preview`：实时渲染文章预览，需要 `post:write` 权限和 `X-CSRF-Token`，只返回渲染后的 HTML，不写入数据库。
- `GET /api/admin/pages`、`GET /api/admin/pages/{id}`、`POST /api/admin/pages`、`PATCH /api/admin/pages/{id}`：后台页面管理，需要 `page:write` 权限，写操作需要 `X-CSRF-Token`。
- `GET /api/admin/friend-link-groups`、`POST /api/admin/friend-link-groups`、`PATCH /api/admin/friend-link-groups/{id}`：友链分组管理，需要 `friend_link:review` 权限，写操作需要 `X-CSRF-Token`。
- `GET /api/admin/friend-links`、`POST /api/admin/friend-links`、`PATCH /api/admin/friend-links/{id}`、`PATCH /api/admin/friend-links/{id}/review`：友链管理和审核，需要 `friend_link:review` 权限，写操作需要 `X-CSRF-Token`。
- `GET /api/admin/site-groups`、`POST /api/admin/site-groups`、`PATCH /api/admin/site-groups/{id}`：小网站导航分组管理，需要 `site_nav:write` 权限，写操作需要 `X-CSRF-Token`。
- `GET /api/admin/site-items`、`POST /api/admin/site-items`、`PATCH /api/admin/site-items/{id}`：小网站导航条目管理，需要 `site_nav:write` 权限，写操作需要 `X-CSRF-Token`；创建和更新会把 `tags_json` 规范化为 `{ "items": ["标签"] }`，最多 8 个标签、单个标签最多 24 个字符。

创建、更新和预览请求体必须是 `content-v1` 加密信封，解密后再进行 Pydantic 字段校验。文章创建和更新可传入 `cover_file_id`、`category_names`、`tag_names`、`seo_title`、`seo_description`、`seo_keywords` 和 `published_at`；后端会自动创建缺失的分类/标签并维护 `post_categories`、`post_tags` 关联。`status=scheduled` 且 `published_at` 晚于当前时间时不会进入公开文章列表或详情；`status=published` 会按 `published_at` 或当前时间公开。创建、更新和发布文章时会把封面文件与正文图片引用同步写入 `file_usages`。`content_html` 由 `markdown-it-py` 渲染 Markdown，启用标题、列表、强调、分隔线、表格等常用语法，`mdit-py-plugins` 保留行内与块级 LaTeX 公式节点，再由 `bleach` 统一执行 HTML sanitize。文章 Markdown 内图片应保存为 `/api/public/posts/{slug}/files/{file_id}/render` 稳定引用；公开文章详情会为实际 HTML 图片地址补上 `expires` 与 `token`，后台实时预览会改写为 `/api/admin/files/{id}/preview` 签名地址，裸访问渲染接口会被拒绝。文章图片和后台预览图片的签名 URL 会在半个有效期时间窗内保持稳定，并返回 `private max-age`、`ETag` 和 `X-Content-Type-Options: nosniff`，让浏览器能复用同一文件的缓存。

## 公开订阅与站点地图

公开分类、标签、文章和页面读取接口使用 public scope `content-v1` 加密响应，调用方需要先协商 `/api/public/encryption/sessions` 并携带 `X-Encryption-Session`：

- `GET /api/public/posts`：返回已公开且已到发布时间的文章列表，支持通过 `category={slug}` 和 `tag={slug}` 按分类、标签筛选；列表响应包含 `items` 和 `total`，供前台直接显示总页数。
- `GET /api/public/friend-links`、`GET /api/public/site-items` 和 `GET /api/public/files`：公开友链、站点目录和公开文件列表响应同样包含 `items` 和 `total`，前台分页不需要额外多取一条记录判断下一页；站点目录条目会返回 `icon_url`、`tags_json` 和 `open_target` 供前台展示图标、标签和打开方式。
- `GET /api/public/site-items/{id}/visit`：公开导航跳转入口，只有公开条目会递增 `click_count` 并 302 跳转到真实 URL，隐藏或私有条目返回 404。友链 URL 只允许 `http/https`；站点导航、站点资料头像和社交入口允许 `http`、`https`、`mailto` 和站内路径，禁止 `javascript:` 等危险协议。
- `GET /api/public/avatar-cache/{token}`：公开头像缓存读取入口。公开站点资料头像和公开友链头像会在列表响应中改写为本站签名缓存 URL，浏览器访问时由后端下载并保存到 `BLOG_UPLOAD_ROOT/avatar-cache`；默认 1 小时内直接复用本地文件，过期后由下一次访问触发重新拉取，拉取失败默认重试 2 次。前端头像组件会把后端返回的头像响应再写入浏览器 Cache Storage，1 小时内优先使用前端缓存。该入口只接受后端签名 token，不提供任意 URL 代理，并在拉取前拒绝 localhost、内网、链路本地和保留地址目标。
- `GET /api/public/categories`：返回已公开且已到发布时间文章使用到的分类，包含 `id`、`name`、`slug` 和 `post_count`。
- `GET /api/public/categories/{slug}`：返回单个公开分类归档信息；分类不存在或没有公开文章时返回 404。
- `GET /api/public/tags`：返回已公开且已到发布时间文章使用到的标签，包含 `id`、`name`、`slug` 和 `post_count`。
- `GET /api/public/tags/{slug}`：返回单个公开标签归档信息；标签不存在或没有公开文章时返回 404。
- `GET /api/public/pages/{slug}`：返回已发布独立页面的标题、正文 HTML 和 SEO 信息；草稿、归档、未发布或不存在页面返回 404。

公开 RSS、sitemap 和 robots.txt 直接挂在根路径，不要求 `X-Encryption-Session`，方便订阅客户端和搜索引擎抓取：

- `GET /rss.xml`：输出 RSS 2.0，站点标题与描述来自公开站点资料，文章条目只包含已公开且已到发布时间的文章。
- `GET /sitemap.xml`：输出 sitemap XML，包含首页、文章列表页、已公开文章永久链接、分类归档页和标签归档页。
- `GET /robots.txt`：允许常规公开内容抓取，屏蔽 `/admin` 与 `/api/admin/`，并声明 sitemap 地址。

这些公开 SEO 端点的绝对 URL 均由 `BLOG_PUBLIC_BASE_URL` 生成；RSS 文章条目会使用发布时间、更新时间、SEO 标题、SEO 描述、分类和标签。RSS、sitemap 和 robots.txt 均返回 `Cache-Control: public, max-age=300, stale-while-revalidate=60` 与 `ETag`；RSS/sitemap 最近渲染结果会短时缓存在应用进程内，客户端命中 `If-None-Match` 时可在查库和 XML 渲染前直接返回 `304` 且不写应用访问日志，正常 `200` 响应仍写入 `access_logs`。

## 后台文件管理

后台文件管理接口已接入 `content-v1` 加密响应，调用方需要携带 `X-Encryption-Session`：

- `GET /api/admin/files`：文件列表，需要 `file:upload` 权限。
- `POST /api/admin/files`：multipart 上传，需要 `file:upload` 权限和 `X-CSRF-Token`。
- `GET /api/admin/files/{id}/temporary-url`：为公开文件生成短时访问链接，需要 `file:upload` 权限。
- `GET /api/admin/files/{id}/download`：后台鉴权下载公开或私有文件，需要 `file:upload` 权限。
- `GET /api/admin/files/{id}/preview`：为后台文章预览提供短时签名图片访问，不用于公开下载。
- `DELETE /api/admin/files/{id}`：软删除文件，需要 `file:delete` 权限和 `X-CSRF-Token`。

当前本地存储驱动会将文件写入 `BLOG_UPLOAD_ROOT`，但不会挂载静态目录，也不会为新文件写入 `/uploads/...` 公开 URL。公开文件栏下载通过后台加密接口按需生成短时签名链接，再由 `/api/public/files/{id}/download?token=...` 校验后返回文件；私有文件不生成公开访问链接，只能通过后台鉴权下载接口读取。文章正文图片渲染使用专门的 `/api/public/posts/{slug}/files/{file_id}/render?expires=...&token=...`，公开封面缩略图使用 `/api/public/posts/{slug}/files/{file_id}/thumbnail?expires=...&token=...`，签名由公开文章详情或后台预览接口按场景颁发，并在时间窗内保持 URL 稳定以命中浏览器缓存。后台文件列表的使用次数来自 `file_usages`，目前文章封面记录为 `cover`，正文图片记录为 `post_body`。上传大小通过 `BLOG_UPLOAD_MAX_SIZE_BYTES` 配置，当前默认 `20971520` 字节，与 Nginx `client_max_body_size 20m` 对齐；当前白名单支持 JPEG、PNG、GIF、WebP 和 PDF，并校验扩展名、MIME、文件头和图片像素边界，图片单边默认不超过 12000 像素且总像素不超过 4000 万，Pillow 解压炸弹警告会视为失败；删除只标记为 `deleted`，由 `cleanup-deleted-files` 在超过保留期且无引用时处理物理文件和数据库记录；本地存储中没有对应 active/deleted 数据库记录的残留文件可先用 `cleanup-orphan-files` dry-run 盘点，再加 `--delete` 清理。短时链接有效期通过 `BLOG_FILE_TEMPORARY_URL_EXPIRE_SECONDS` 配置。公开文件列表、公开文件下载、文章图片渲染、文章缩略图、后台短时链接生成和后台文件下载成功访问都会写入访问日志，并按 IP、方法和 path 做短时去重。

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

真实运行库 HTTP 闭环验证可使用 `scripts/verify_runtime_publish_flow.py`。脚本需要本地后端服务已通过 `uv run python main.py` 启动，并通过 `BLOG_VERIFY_ADMIN_USERNAME` 与 `BLOG_VERIFY_ADMIN_PASSWORD` 提供后台管理员凭据；前端稳定路由、后台列表分页和 SEO 元信息检查还需要前端服务已启动，前端地址可通过 `BLOG_VERIFY_FRONTEND_URL` 配置，默认 `http://127.0.0.1:15173`，浏览器通道可通过 `BLOG_VERIFY_BROWSER_CHANNEL` 配置，默认 `msedge`。它会按真实接口协商 `sensitive-v1` / `content-v1` 加密会话，完成后台登录、公开和私有图片上传、文章实时预览、创建并发布文章、创建公开页面、分类、标签、SEO 信息、未来定时文章不提前公开、公开文章列表和详情封面缩略图、公开页面详情、分类/标签详情、分类/标签筛选、RSS、sitemap、robots.txt、前端文章和页面 SEO 元信息、正文图片渲染、公开文件栏下载、私有文件不进入公开列表、后台私有文件鉴权下载、文件引用追踪、后台文章/文件列表分页、公开友链申请、后台友链分组与审核通过/拒绝、公开友链展示与拒绝项排除、小网站导航分组和条目创建、图标/标签/打开方式公开展示、公开跳转 302 与点击统计、`/links` 和 `/sites` 桌面/移动端 Playwright 页面检查，以及访问日志查询；默认验证完成后把测试文章和页面归档、把验证友链改为拒绝并隐藏验证导航条目和分组，传入 `--keep-published` 可保留文章和页面公开状态。

公开页分页与移动端密度回归可使用 `scripts/verify_public_page_pagination.py`。脚本需要本地后端和前端服务已启动，默认检查 `BLOG_VERIFY_FRONTEND_URL` 或 `http://127.0.0.1:15173`，并使用 `BLOG_VERIFY_BROWSER_CHANNEL` 或默认 `msedge` 启动 Playwright Chromium 通道。脚本会在当前数据库中写入随机前缀临时友链、站点目录和公开文件，检查 `/links?page=2`、`/sites?page=2`、`/files?page=2` 在桌面和移动端视口下均能显示第二页分页条且无横向溢出，最后清理临时数据并输出 `remaining_seed_rows`。

## 部署目标

生产部署环境为 Linux Debian，使用 Docker Compose、Nginx、MySQL 和私有容器网络。公网只允许 Nginx 暴露 `80/443`。
