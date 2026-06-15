# 项目进度

## 2026-06-16

### 已完成

- 新增后端 `RateLimitService` 与单进程内存限流器，登录入口和加密协商入口已接入可配置限流。
- 限流命中会返回 `429`，携带 `Retry-After`，并写入 `security_events` 安全事件日志。
- 新增后台日志查询接口：`GET /api/admin/audit-logs`、`GET /api/admin/login-logs`、`GET /api/admin/security-events`，统一需要 `audit_log:read` 权限。
- 新增日志 Repository、Service 和响应 schema，保持 API、业务和数据库访问分层。
- 新增 `BLOG_ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS`、`BLOG_ADMIN_LOGIN_RATE_LIMIT_WINDOW_SECONDS`、`BLOG_ENCRYPTION_SESSION_RATE_LIMIT_MAX_ATTEMPTS`、`BLOG_ENCRYPTION_SESSION_RATE_LIMIT_WINDOW_SECONDS` 配置，并同步后端与部署环境变量示例。
- 补充限流服务、限流命中安全事件和后台登录日志查询接口测试。
- 更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，记录后台日志查询、入口限流和生产替换风险。
- 新增后台文章管理接口：`GET /api/admin/posts`、`POST /api/admin/posts`、`GET /api/admin/posts/{id}`、`PATCH /api/admin/posts/{id}`、`POST /api/admin/posts/{id}/publish`。
- 新增后台页面管理接口：`GET /api/admin/pages`、`POST /api/admin/pages`、`GET /api/admin/pages/{id}`、`PATCH /api/admin/pages/{id}`。
- 文章和页面管理接口响应已接入 `content-v1` 加密信封，写操作沿用后台 CSRF 防护和权限依赖。
- 新增内容 Repository、Service、schema 和临时安全 Markdown 渲染 Provider，先生成转义后的段落 HTML，后续替换为正式 Markdown/LaTeX 渲染与 sanitize 策略。
- 前端 API client 新增 `apiPatchEncrypted`，为后续后台文章和页面编辑页复用 `content-v1` 加密响应解密流程。
- 补充内容服务测试和后台内容 API 加密响应测试。
- 新增 `EncryptedApiRequest`、后端加密请求解密流程和前端请求体加密能力，后台文章与页面创建/更新请求已改为 `content-v1` 加密信封。
- 补充后台文章创建接口测试，覆盖 CSRF、`content-v1` 请求解密和响应加密路径。
- 将内容 HTML 生成从临时安全渲染器替换为 `markdown-it-py` + `mdit-py-plugins` + `bleach`：支持 Markdown、行内公式 `$...$`、块级公式 `$$...$$`，并统一执行 HTML sanitize。
- 新增 `bleach`、`markdown-it-py`、`mdit-py-plugins` 后端运行依赖，并更新 `uv.lock`。
- 补充 Markdown 渲染 Provider 测试，覆盖基础 Markdown、LaTeX 公式节点、危险 HTML 和危险链接清洗。
- 新增前端后台内容 API 封装，文章和页面列表、创建、更新、文章发布均复用 `content-v1` 加密响应解密，写操作使用 `content-v1` 加密请求体和 CSRF Token。
- 新增后台文章管理页 `/admin/posts`，支持文章列表、新建、编辑、发布、状态/可见性/SEO 字段编辑和后端 sanitize 后的 HTML 预览。
- 新增后台页面管理页 `/admin/pages`，支持页面列表、新建、编辑、导航显示、排序和 SEO 字段编辑。
- 后台侧边栏和权限路由新增“文章”“页面”入口，分别绑定 `post:read` / `post:write` / `post:publish` 与 `page:write` 权限。
- 更新后台内容表单、列表和预览样式，沿用当前 Yohaku 中性色、细边框和紧凑管理界面层级。
- 前后端联调发现后台浏览器请求会被 CORS 预检拦截，已将 `X-Encryption-Session` 加入后端 CORS 允许请求头，并补充预检测试。
- 前后端联调发现内容创建响应在读取 `created_at` / `updated_at` 时触发 SQLAlchemy async 隐式 IO，已在内容服务提交后显式 refresh 返回对象。
- 前端联调发现 slug 输入的 `pattern` 在新版浏览器 `v` 正则模式下对未转义连字符报错，已修正文章和页面表单 slug pattern。
- 验证首页文章展示链路，确认当前首页仍读取前端 `samplePosts` 示例数据，后台新增并发布的文章不会出现在首页。
- 新增公开文章 API：`GET /api/public/posts` 与 `GET /api/public/posts/{slug}`，仅返回已发布、公开且未删除的文章。
- 公开文章列表响应不返回正文 HTML，详情响应返回后端 sanitize 后的 `content_html`。
- 前端首页“近期笔墨”和 `/posts` 文章列表已从 `samplePosts` 切换到真实 Public API，并补充加载、空列表和接口不可用状态。
- 新增公开文章详情页 `/posts/:slug`，支持展示发布时间、阅读时长、摘要和正文 HTML。
- 补充公开文章 API 测试与内容服务公开查询测试。
- 新增前端 `MathHtml` 组件，统一将后端 sanitize 后的 `.math.inline` / `.math.block` 节点交给 KaTeX 渲染。
- 前台文章详情、后台文章预览和后台页面预览已接入 KaTeX 公式渲染，页面管理补充了后端 HTML 预览栏。
- 后台内容管理界面补充 sticky 列表/预览、正文预览排版、公式块横向滚动和窄屏取消 sticky 的响应式处理。
- 已按用户要求将后续 Git 节奏调整为完成可验证小步后自动 commit 并 push。

### 进行中

- M1 认证与后台框架继续推进；后台登录、Cookie 会话、CSRF、权限菜单、`sensitive-v1` 加密响应、后台日志查询、入口限流、后台文章与页面管理接口已形成第一版后端闭环，文章与页面后台前端已接入 `content-v1` 加密列表、创建、更新、文章发布、后端 HTML 预览和 KaTeX 公式渲染流程，公开前台已接入已发布文章列表与详情读取链路。

### 阻塞与风险

- 待确认真实域名、服务器环境、证书申请方式和对象存储选择。
- 当前限流器为单进程内存实现，适合 M1 单进程验证；生产多进程、多实例或横向扩展前，需要替换为 Redis 等共享存储适配器。
- 应用层加密协商已改为数据库保存短期会话密钥；仍需补充过期会话定时清理和更多审计记录。
- 公开文章链路已接入真实 Public API，但本次尚未重新启动本机 MySQL 临时库做后台发布到前台展示的端到端联调。
- 本次已启动前后端和本机 MySQL 临时库完成真实登录、加密协商、文章创建、文章发布和页面创建联调；联调后按要求关闭前后端开发服务。
- 本次按用户最新要求，完成可验证小步后自动 commit 并 push。

### 下一步

- 继续实现文件和后台设置的最小 CRUD。
- 补充加密会话过期清理任务，并评估 Redis 限流适配器。
- 使用真实 MySQL 临时库重新做“后台发布文章 -> 前台首页、列表、详情可见”的端到端联调。

### 验证

- 已运行 `uv run ruff check .`，通过。
- 已运行 `uv run pytest`，39 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 已运行 `uv run alembic upgrade head --sql`，迁移升级 SQL 可生成。
- 已运行 `npm.cmd run lint`，通过。
- 已运行 `npm.cmd run build`，通过。
- 本次后台内容前端接入后已重新运行 `npm.cmd run lint`，通过。
- 本次后台内容前端接入后已重新运行 `npm.cmd run build`，通过。
- 本次前后端联调修复后已重新运行 `uv run ruff check .`，通过。
- 本次前后端联调修复后已重新运行 `uv run pytest`，39 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 本次前后端联调修复后已重新运行 `npm.cmd run lint`，通过。
- 本次前后端联调修复后已重新运行 `npm.cmd run build`，通过。
- 已使用本机 MySQL 临时库 `blog_codex_verify` 运行 Alembic 迁移并创建临时管理员，通过 Playwright CLI 验证后台登录、`/admin/posts` 文章创建与发布、`/admin/pages` 页面创建。
- 联调完成后已关闭本项目启动或复用的前端 `15173` 与后端 `18080` 开发服务，确认两端口不再监听；已删除本机 MySQL 临时库 `blog_codex_verify`。
- 已启动前端并通过 Playwright CLI 打开首页，确认“近期笔墨”仍展示 `samplePosts` 的三篇示例文章，未出现后台联调新增的“校验文章”；验证后关闭前端开发服务。
- 公开文章链路接入后已重新运行 `uv run ruff check .`，通过。
- 公开文章链路接入后已重新运行 `uv run pytest`，43 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 公开文章链路接入后已重新运行 `npm.cmd run lint`，通过。
- 公开文章链路接入后已重新运行 `npm.cmd run build`，通过。
- 已启动前端预览服务并通过 Playwright CLI + Microsoft Edge 检查 `/`、`/posts`、`/posts/public-post`，确认公开路由均可渲染；由于本次未启动后端，页面按预期显示文章服务暂时不可用或文章未找到状态，控制台 fetch 错误来自后端 `18080` 未监听。验证后已关闭前端预览服务，确认 `14173` 不再监听。
- KaTeX 渲染接入后已重新运行 `npm.cmd run lint`，通过。
- KaTeX 渲染接入后已重新运行 `npm.cmd run build`，通过；构建产物包含 KaTeX 字体资源，Vite 提示主 chunk 超过 500KB，后续可按路由懒加载优化。
- KaTeX 渲染接入后已重新运行 `git diff --check`，通过。
- 已临时启动后端 `18080` 与前端 `15173`，通过 Playwright CLI + Microsoft Edge 登录后台，创建含 `$E=mc^2$` 的文章草稿，确认后台文章 HTML 预览中公式由 KaTeX 渲染；验证后已关闭前后端服务，确认 `18080` 与 `15173` 不再监听。

## 2026-06-15

### 已完成

- 前台 UI 按 Innei/Yohaku 风格重做，新增 `@yohaku/design-system` 设计契约依赖，并在 `frontend/src/index.css` 中镜像 Yohaku token。
- 重做公开首页 `/`：纸面背景、雨线氛围、头像身份区、引文统计、圆形社交入口、Recent Writing 时间线、碎念/来信双栏和底部浮动导航。
- 重做公开内页 `/posts`、`/links`、`/sites`：统一大留白标题区、serif 中文标题、低对比说明文字、细分隔线列表和 Yohaku 状态标签。
- 同步调整 `/admin/login` 和后台工作台视觉：使用同一套中性色、梅色 accent、细边框、轻玻璃和 serif 标题层级。
- 将 `AuthProvider` 从全站根节点移动到后台路由分支，避免公开页面在后端未启动时请求后台加密会话接口。
- 更新 `frontend/index.html` 页面标题为“静默书房”。
- 创建 `PROJECT_PLAN.md`，完成个人博客系统项目计划书。
- 将架构升级为公网部署优先设计，补充 HTTPS、Nginx、内网隔离、备份、监控和安全基线。
- 补充面向对象、设计模式、解耦、单文件体量和重构要求。
- 创建 `AGENT.md`，固化后续开发协作规范。
- 补充版本号规则：项目版本采用 `X.Y.Z`，Git tag 和发布名称采用 `vX.Y.Z`，非正式版一律 `v0.y.z`。
- 补充 Git/GitHub 管理规则：默认 `main` 分支，改动后必须 commit 并 push。
- 已通过 `winget` 安装 GitHub CLI `2.94.0`。
- 已确认 GitHub CLI 登录账号 `ChaceQC`。
- 已确认远端仓库 `ChaceQC/blog` 尚未存在。
- 新增 `.gitignore`，覆盖环境变量、密钥、依赖目录、构建产物、上传文件、备份和本地运行数据。
- 在 `PROJECT_PLAN.md` 和 `AGENT.md` 中补充 `.gitignore` 与依赖锁文件管理规则。
- 已将本地默认分支调整为 `main`。
- 已创建 GitHub 私有仓库 `ChaceQC/blog`，并配置 `origin` remote。
- 已创建初始提交并推送 `main` 分支到 GitHub。
- 更新提交说明规范：后续 commit message 统一使用中文说明，可保留英文类型前缀。
- 按最新协作要求补充开发环境为 Windows 11，生产部署环境为 Linux Debian。
- 补充分支与提交节奏：日常开发使用 `dev` 分支，一个完整功能完成后再合并到 `main`，实现过程按可验证小步 commit 并 push。
- 已创建并切换到本地 `dev` 分支，后续开发在 `dev` 上推进。
- 按最新协作要求补充语言规范：界面文案、说明文字、代码注释、README 和项目文档默认使用中文。
- 补充文件命名规范：真实文件路径、目录名、对象 key、代码导入路径和真实存储文件名使用英文，中文文件名作为展示名等单独字段保存。
- 初始化 `backend` 后端工程，使用 `uv` 管理 FastAPI 依赖和开发工具。
- 创建后端 `app` 分层结构：`api`、`core`、`models`、`schemas`、`services`、`repositories`、`providers`、`tasks`。
- 实现 FastAPI 应用工厂、Trusted Host、CORS、安全配置校验、结构化日志、数据库连接和 `/healthz`、`/readyz` 健康检查。
- 按计划书拆分用户权限、文章页面、文件、友链、导航站点、系统设置和日志相关 SQLAlchemy 模型。
- 初始化 Alembic 目录，并将迁移环境接入应用配置与 SQLAlchemy metadata。
- 初始化 `frontend` 前端工程，使用 React + TypeScript + Vite + npm。
- 创建前台路由骨架：首页、文章列表、友链、站点导航。
- 创建后台路由骨架：后台布局、侧边栏、内容状态、最近文章和文件队列预览。
- 清理 Vite 默认示例页面和默认素材，替换为中文 README、中文界面文案和项目 favicon。
- 前端文件示例已按规则拆分为英文 `objectKey` 和中文 `displayName`。
- 新增部署骨架：`deploy/docker-compose.yml`、`deploy/docker-compose.prod.yml`、Nginx 镜像模板、环境变量示例和部署说明。
- 新增 MySQL 备份、恢复和 Let's Encrypt 证书申请/续期脚本。
- 新增 `.gitattributes`，强制 shell、Compose、Dockerfile 等工程文件使用 LF 行尾，适配 Debian 部署。
- 修正 `.gitignore`，确保 `deploy/env/*.env` 被忽略但 `deploy/env/*.env.example` 可提交。
- 测试完成后已关闭本项目启动的 Vite 开发服务器，确认 `127.0.0.1:5173` 不再监听；`127.0.0.1:3000` 为 QQ 进程，未关闭。
- 补充本地开发端口规范：避免使用常见端口，前端默认 `15173`，后端默认 `18080`。
- 补充配置外置规范：端口、域名、数据库连接、CORS、Trusted Host、上传目录、API 地址等配置必须放在独立配置文件或环境变量中。
- 新增 `backend/.env.example`，后端本地端口、数据库连接、CORS、Trusted Host、上传目录等配置通过 `Settings` 从 `.env.example` 或 `.env` 读取。
- 新增 `frontend/config/development.json`，前端开发端口、预览端口和 API 地址由 Vite 配置读取，不再写死在 `package.json` 启动脚本中。
- 更新 `deploy/env/backend.env.example`，补齐后端运行所需配置字段。
- 新增根目录 `README.md`，记录整个项目总览、当前阶段、目录结构、本地开发、验证命令、部署边界和文档维护规则。
- 在 `AGENT.md` 和 `PROJECT_PLAN.md` 中补充要求：实现、重构、测试、部署配置或规则变化时，必须实时更新 `README.md`、`PROJECT_PLAN.md`、`PROJECT_PROGRESS.md` 和 `AGENT.md` 中受影响的内容。
- 新增初始 Alembic 迁移 `20260615_0001_initial_schema.py`，覆盖用户权限、文章页面、文件管理、友链、站点导航、系统设置和日志相关数据表。
- 初始迁移已处理 `users.avatar_file_id` 与 `files.uploader_id` 的循环外键，建表后再补加用户头像外键。
- 更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，标记 M0 脚手架与初始迁移完成，并将下一步调整为 M1 认证与后台框架。
- 已将初始迁移作为第二个小步提交并推送到 `dev`，确认 `main` 可安全快进后，已用 `--ff-only` 将 `main` 快进到 `dev` 并推送。
- 新增后端后台认证接口：`POST /api/admin/auth/login`、`POST /api/admin/auth/refresh`、`POST /api/admin/auth/logout`。
- 新增认证核心工具，支持 Argon2id 密码校验、短期 Access Token 签发、Refresh Token 生成和哈希。
- 新增认证 Repository、Service 和 Policy 边界，登录成功记录登录日志，Refresh Token 支持存库、轮换和吊销。
- 新增认证请求/响应 schema，并将后台认证路由接入 `/api/admin`。
- 新增认证服务测试，覆盖登录成功、密码错误、刷新令牌轮换和退出吊销。
- 更新 `backend/.env.example` 和 `deploy/env/backend.env.example`，补充 Access Token 与 Refresh Token 有效期配置。
- 新增 `uv run python -m app.cli create-admin` 初始管理员创建命令，支持交互式输入密码。
- 新增初始管理员创建 Service 与 Repository，自动创建 `super_admin` 角色并绑定管理员用户。
- 新增初始管理员创建测试，覆盖创建用户、角色绑定和重复用户名拒绝。
- 新增 `cryptography` 后端运行依赖，支持 `asyncmy` 连接 MySQL 8 默认 `caching_sha2_password` 认证账号。
- 已使用根目录本地机密文件 `auth.txt` 中的 Windows MySQL root 凭据完成本机 MySQL 验证；该文件已加入 `.gitignore`，不会提交。
- 新增前端后台登录页 `/admin/login`、本地会话保存、后台路由保护和退出登录逻辑。
- 扩展前端 API client，支持后台认证 POST 请求。
- 使用 Playwright CLI + Microsoft Edge 检查 `/admin` 未登录重定向到 `/admin/login`，并保存本地截图到已忽略的 `output/playwright`。
- 更新 `.gitignore`，忽略 `auth.txt`、`.playwright-cli/` 和 `output/` 本地产物。
- 更新 `PROJECT_PLAN.md`，明确文章和页面正文支持 Markdown 与 LaTeX 公式语法，渲染结果必须统一做 HTML sanitize。
- 更新根目录 `README.md` 和后端 `README.md`，记录 Windows 本机 MySQL 可用于临时库真实迁移、初始管理员和认证流程验证；`auth.txt` 仅作本地机密文件使用，禁止提交。
- 新增后台当前用户接口 `GET /api/admin/auth/me` 和可复用 Bearer Token 鉴权依赖。
- 认证服务新增 Access Token 解析与当前用户加载能力，当前用户响应复用角色和权限聚合逻辑。
- 前端登录态启动时会通过 Cookie 调用当前用户接口恢复会话，失效 session 会自动进入未登录状态。
- 将浏览器后台会话从 `localStorage` Token 调整为 HttpOnly Cookie，前端不再持久保存 Access Token 和 Refresh Token。
- 新增后台 CSRF 双提交校验，刷新和退出等写操作需要携带 `X-CSRF-Token`。
- 新增后台权限依赖 `require_admin_permission`，并补充 CSRF、权限和会话响应安全测试。
- 前端后台菜单按当前用户权限过滤，直接访问无权限子路由时显示权限不足状态。
- 在 `PROJECT_PLAN.md` 中补充应用层加密传输规划：敏感后台数据使用 `sensitive-v1`，文章/页面/草稿等内容使用 `content-v1`，公开已发布文章仍兼顾 SEO 和缓存。
- 新增后端应用层加密信封基础 `backend/app/core/encryption.py`，提供 `sensitive-v1` 与 `content-v1` 两套独立 profile、HKDF 派生上下文和 AES-GCM JSON 信封。
- 新增后端应用层加密协商接口 `POST /api/admin/encryption/sessions`，使用浏览器兼容的 P-256 ECDH 生成短期会话密钥。
- 后端认证接口 `POST /api/admin/auth/login`、`POST /api/admin/auth/refresh` 和 `GET /api/admin/auth/me` 已支持请求携带 `X-Encryption-Session` 时返回 `sensitive-v1` 加密信封。
- 前端新增 WebCrypto 协商与解密工具，后台登录和当前用户恢复流程已接入 `sensitive-v1` 解密；`content-v1` 解密基础已可供后续文章、页面和草稿管理接口复用。
- 新增 `BLOG_ENCRYPTION_SESSION_EXPIRE_SECONDS` 配置，并同步 `backend/.env.example` 和 `deploy/env/backend.env.example`。
- 新增后端集成测试，覆盖协商短期密钥后解开登录接口返回的 `sensitive-v1` 加密信封。
- 更新 `README.md` 和 `PROJECT_PLAN.md`，记录加密协商接口、当前接入范围和数据库会话存储要求。
- 新增加密会话数据表 `encryption_sessions`、SQLAlchemy 模型、Repository 和 Alembic 迁移，开发环境与生产环境均通过数据库保存短期应用层加密会话。
- 移除认证接口的旧明文 JSON 响应形态，登录、刷新和当前用户接口现在强制要求 `X-Encryption-Session` 并返回 `sensitive-v1` 加密信封。
- 前端 encrypted API client 移除明文响应兜底，收到非加密响应会直接报错。
- 更新后端 `README.md`，同步加密协商、强制加密响应和最新迁移验证命令。

### 进行中

- M1 认证与后台框架正在推进，后台登录、Cookie 会话、CSRF、当前用户校验、菜单权限状态和 `sensitive-v1` 加密响应已形成第一版闭环。

### 阻塞与风险

- 待确认真实域名、服务器环境、证书申请方式和对象存储选择。
- 真实 MySQL 验证已在临时库完成；生产数据库迁移仍需在正式环境备份后执行。
- 应用层加密协商已改为数据库保存短期会话密钥；仍需补充过期会话定时清理、审计记录和限流。
- `content-v1` 已具备前端解密基础，但尚未接入实际文章、页面和草稿 CRUD 接口。

### 下一步

- 补充认证审计日志查询、加密协商接口限流、登录接口限流和限流命中日志。
- 将 `content-v1` 接入文章、页面和草稿管理接口，继续实现文章、文件、设置的最小 CRUD。

### 验证

- 已检查文档文件创建和 Git 工作区状态。
- 已验证 GitHub CLI 可通过 `C:\Program Files\GitHub CLI\gh.exe` 执行。
- 已检查 `.gitignore` 规则，确认 `uv.lock` 和 `package-lock.json` 不被忽略。
- 已验证 `.env`、`uploads/`、`backups/` 会被 `.gitignore` 忽略。
- 已运行 `uv run ruff check .`，通过。
- 已运行 `uv run pytest`，2 个健康检查测试通过；存在 FastAPI TestClient 依赖的上游弃用警告。
- 已运行 `npm run lint`，通过。
- 已运行 `npm run build`，通过。
- 已通过浏览器检查 `http://127.0.0.1:5173/admin`，确认中文界面、`zh-CN` 页面语言、中文展示名和英文文件路径展示正常。
- 已运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config`，配置可展开；确认公网端口只映射到 Nginx。
- 已使用 `C:\Program Files\Git\bin\bash.exe -n` 检查部署脚本语法，通过。
- 已检查本地监听端口，确认本项目开发服务器已关闭。
- 配置外置调整后已重新运行 `uv run ruff check .`、`uv run pytest`、`npm run lint`、`npm run build`，均通过。
- 已再次检查 `15173`、`18080`、`14173`、`5173`、`8000`，确认没有开发服务器监听。
- 已运行 `uv run alembic upgrade head --sql`，初始迁移升级 SQL 可生成。
- 已运行 `uv run alembic downgrade 20260615_0001:base --sql`，初始迁移回滚 SQL 可生成。
- 初始迁移新增后已重新运行 `uv run ruff check .`，通过。
- 初始迁移新增后已重新运行 `uv run pytest`，2 个健康检查测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 已运行 `git diff --check`，未发现空白或行尾问题。
- 已确认 `main...dev` 与 `origin/main...origin/dev` 均为 `0 9`，`main` 可安全快进到 `dev`。
- 已运行 `git merge --ff-only dev`，`main` 快进成功并推送到 `origin/main`。
- 后端认证第一小步已运行 `uv run ruff check .`，通过。
- 后端认证第一小步已运行 `uv run pytest`，认证服务和健康检查共 7 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 初始管理员创建小步已运行 `uv run ruff check .`，通过。
- 初始管理员创建小步已运行 `uv run pytest`，认证服务、初始管理员创建和健康检查共 9 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 已运行 `uv run python -m app.cli --help`，CLI 入口可正常加载。
- 已在本机 MySQL 临时库 `blog_codex_migration_test` 上运行 `uv run alembic upgrade head`，真实建表通过。
- 已在本机 MySQL 临时库运行 `uv run python -m app.cli create-admin`，初始管理员创建通过。
- 已在本机 MySQL 临时库通过服务层完成登录、刷新令牌和退出流程；本地开发密钥偏短时会触发 PyJWT 安全长度警告，测试已改用 32 位以上临时密钥。
- 已在本机 MySQL 临时库运行 `uv run alembic downgrade base`，真实回滚通过；回滚后临时库仅剩 Alembic 版本表，随后已删除整个临时库。
- 前端登录页小步已运行 `npm.cmd run lint`，通过。
- 前端登录页小步已运行 `npm.cmd run build`，通过。
- 已使用 Playwright CLI 打开 `http://127.0.0.1:15173/admin` 并确认重定向到 `/admin/login`。
- 已通过截图检查后台登录页视觉状态，未发现空白或明显布局错位。
- 文档补充后已运行 `git diff --check`，未发现空白或行尾问题。
- 当前用户接口小步新增后端认证服务测试，覆盖有效 Access Token 返回当前用户、无效 Access Token 拒绝。
- 当前用户接口小步新增健康路由测试，覆盖未携带 Bearer Token 访问 `/api/admin/auth/me` 返回 401。
- 当前用户接口小步已运行 `uv run ruff check .`，通过。
- 当前用户接口小步已运行 `uv run pytest`，认证服务、初始管理员创建和健康检查共 12 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 当前用户接口小步已运行 `npm.cmd run lint`，通过。
- 当前用户接口小步已运行 `npm.cmd run build`，通过。
- 当前用户接口小步已运行 `git diff --check`，未发现空白或行尾问题。
- Cookie 会话、CSRF 和权限菜单小步已运行 `uv run ruff check .`，通过。
- Cookie 会话、CSRF、权限菜单和加密信封小步已运行 `uv run pytest`，认证服务、初始管理员创建、后台安全、加密信封和健康检查共 22 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- Cookie 会话、CSRF 和权限菜单小步已运行 `npm.cmd run lint`，通过。
- Cookie 会话、CSRF 和权限菜单小步已运行 `npm.cmd run build`，通过。
- Cookie 会话、CSRF、权限菜单和加密信封小步已运行 `git diff --check`，未发现空白或行尾问题。
- 加密协商和前端解密接入后已运行 `uv run ruff check .`，通过。
- 加密协商和前端解密接入后已运行 `uv run pytest`，23 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 加密协商和前端解密接入后已运行 `npm.cmd run lint`，通过。
- 加密协商和前端解密接入后已运行 `npm.cmd run build`，通过。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `uv run ruff check .`，通过。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `uv run pytest`，24 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `uv run alembic upgrade head --sql`，迁移升级 SQL 可生成。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `uv run alembic downgrade 20260615_0002:20260615_0001 --sql`，迁移回滚 SQL 可生成。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `npm.cmd run lint`，通过。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `npm.cmd run build`，通过。
- 加密会话改为数据库存储并移除旧响应形态后已运行 `git diff --check`，未发现空白或行尾问题。
- Yohaku UI 重做后已运行 `npm.cmd run lint`，通过。
- Yohaku UI 重做后已运行 `npm.cmd run build`，通过。
- 已使用 Playwright CLI + Microsoft Edge 对 `http://127.0.0.1:15173/`、`/posts`、`/links`、`/sites`、`/admin/login` 截图检查，截图保存到已忽略的 `output/playwright`。
