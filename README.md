# 个人博客系统

这是一个自托管个人博客与轻量 CMS 项目。系统面向公网部署设计，包含支持 Markdown 与 LaTeX 公式的文章发布、文件管理、友链、小网站导航和后台管理能力。

## 当前阶段

当前版本处于 `v0.1.0` 脚手架阶段，开发分支为 `dev`。M0 脚手架、生产部署骨架和初始 Alembic 迁移已完成，M1 已落地后台登录、当前用户接口、初始管理员创建命令、Cookie 会话、CSRF 防护、前端权限菜单、后台日志查询、后台文章与页面管理接口、后台文件上传与管理接口、后台友链/导航/设置接口、公开文章列表与详情读取链路、公开站点资料读取、公开文件栏、前台与后台 KaTeX 公式渲染，以及 `sensitive-v1` / `content-v1` 应用层加密协商基础。后台文章编辑已支持不保存草稿也能通过真实 API 更新 HTML 预览，文章保存时会同步记录封面文件和正文图片引用；文章封面已可在后台从公开图片文件中搜索和分页选择，选择器只加载后台缩略图，并在前台文章列表与详情中展示，公开页封面 URL 也会使用带签名的缩略图地址，无封面文章会加载默认封面。首页“近期笔墨”最多展示 3 篇，文章列表页已支持每页 5 篇分页；公开友链、站点目录、公开文件以及后台文章、页面、文件、友链、导航和日志列表已开始采用分页浏览；后台站点资料页已改为分区标签，减少新增字段直接向页面底部堆积。首页碎念和社交入口已可通过后台站点资料维护。后台维护任务已开始形成独立入口，当前可通过 CLI 清理过期应用层加密会话和已软删除且无引用的本地文件；后台文件详情已支持通过后台鉴权下载公开或私有文件。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、uv。
- 前端：React、TypeScript、Vite、npm、Yohaku 设计系统 token。
- 数据库：MySQL 8。
- 缓存：Redis，可选启用。
- 部署：Linux Debian、Docker Compose、Nginx、Let's Encrypt。
- 开发环境：Windows 11。

## 目录结构

```text
backend/              后端 FastAPI 工程
frontend/             前端 React 工程
deploy/               Debian 生产部署配置
AGENT.md              开发协作规则
PROJECT_PLAN.md       项目计划书
PROJECT_PROGRESS.md   项目进度记录
README.md             项目总览文档
```

## 本地开发

本地开发服务避免使用常见端口。端口、API 地址、数据库连接、CORS、Trusted Host、上传目录等配置必须来自独立配置文件或环境变量。

- 前端默认端口：`15173`，配置文件为 `frontend/config/development.json`。
- 前端预览端口：`14173`，配置文件为 `frontend/config/development.json`。
- 后端默认端口：`18080`，配置文件为 `backend/.env`。
- 后端本地启动统一使用 `uv run python main.py`，不要直接用系统 Python 或全局 Python 启动。
- 浏览器联调或接口验证结束后，关闭本次启动的前端、后端或预览服务，并确认相关端口不再监听。

后端：

```powershell
cd backend
uv sync
Copy-Item .env.example .env
uv run python main.py
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

前台 UI 以 Innei/Yohaku 的个人站视觉语言为基线：纸面背景、Pure 中性色、梅色 accent、底部浮动导航、serif 标题、细分隔线列表和低对比内容模块。`@yohaku/design-system` 作为设计契约依赖，运行时样式在 `frontend/src/index.css` 中镜像 Yohaku token，避免当前非 Tailwind 构建链直接处理 `@theme` 规则产生警告。

## 验证命令

后端：

```powershell
cd backend
uv run ruff check .
uv run pytest
$env:PYTHONUTF8='1'
uv run alembic upgrade head --sql
uv run alembic downgrade 20260615_0002:20260615_0001 --sql
uv run python -m app.cli --help
uv run python -m app.cli cleanup-encryption-sessions
uv run python -m app.cli cleanup-deleted-files --older-than-days 7 --limit 100
```

前端：

```powershell
cd frontend
npm run lint
npm run build
```

部署配置：

```powershell
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config --quiet
```

本地 MySQL 验证：

Windows 本机安装 MySQL 8 时，可以用本地临时库验证真实迁移、初始管理员创建和后台认证流程。浏览器后台会话使用 HttpOnly Cookie 保存 Access Token 和 Refresh Token，前端只保留内存中的用户信息与 CSRF Token；写操作通过 `X-CSRF-Token` 校验。后台前端会通过 `/api/admin/encryption/sessions` 协商短期 P-256 ECDH 会话密钥，会话密钥保存到 `encryption_sessions` 数据表；登录、当前用户、刷新和后台日志接口必须返回 `sensitive-v1` 加密信封，不再保留旧的明文 JSON 响应形态。登录和加密协商入口已有第一版可配置限流，命中会写入 `security_events`；公开内容读取、公开文件下载、文章图片渲染、后台短时链接生成和后台文件下载会写入 `access_logs`，后台“日志”页可查看详情。后台文章与页面管理接口的创建、更新请求和响应已接入 `content-v1` 加密信封，前端 `/admin` 总览和 `/admin/posts` 已读取真实后台文章数据，`/admin/pages` 已接入加密列表、创建和更新流程；后台文章预览通过 `POST /api/admin/posts/preview` 走真实 Markdown 渲染和 HTML sanitize，但不写入数据库。文章创建、更新和发布会把 `cover_file_id` 与正文中的 `/api/public/posts/{slug}/files/{file_id}/render` 图片引用同步写入 `file_usages`，供后台文件列表统计和后续清理任务使用。后端生成的 `math inline/block` 节点会在前台文章详情与后台预览中用 KaTeX 渲染。后台 `/admin/files` 已通过 `content-v1` 接入文件列表、上传、软删除和短时访问链接生成接口，上传限制通过 `BLOG_UPLOAD_MAX_SIZE_BYTES` 配置，当前白名单支持 JPEG、PNG、GIF、WebP 和 PDF；文件详情可复制文章 Markdown 引用，也可通过后台鉴权直接下载公开或私有文件。`cleanup-deleted-files` 维护命令会按保留天数清理已软删除、无 `file_usages` 引用且路径安全的本地文件，并删除对应数据库记录。文章正文图片使用 `/api/public/posts/{slug}/files/{file_id}/render` 稳定引用，公开文章详情会为实际图片响应补上 `expires` 与 `token`，后台预览则使用 `/api/admin/files/{id}/preview` 短时签名链接，不依赖静态目录或临时下载链接。`/admin/settings` 已通过 `sensitive-v1` 接入真实站点基础设置读取与保存接口，公开首页、公开布局品牌、后台布局品牌和页面标题会读取 `/api/public/settings/site-profile`。`/admin/links` 已通过 `content-v1` 接入友链列表、创建、编辑、审核状态更新和导航条目读取、创建、编辑。公开前台通过 `/api/public/encryption/sessions` 协商 public scope 会话，文章、友链、站点目录、站点资料和公开文件栏读取接口均使用 `content-v1` 加密响应；公开文件不挂载静态目录，公开文件栏下载由后台按需生成带签名和过期时间的 `/api/public/files/{id}/download` 访问链接，私有文件只能通过后台鉴权下载。根目录 `auth.txt` 可保存本机 MySQL root 凭据供本地验证使用，该文件属于机密文件，已被 `.gitignore` 忽略，禁止提交。

建议只操作临时库，例如 `blog_codex_migration_test`：创建临时库后临时设置 `BLOG_DATABASE_URL`，运行 `uv run alembic upgrade head`、`uv run python -m app.cli create-admin ...`，验证完成后运行 `uv run alembic downgrade base` 并删除临时库。

## 部署边界

生产部署目标为 Linux Debian。公网只允许 Nginx 暴露 `80/443`，后端、MySQL、Redis 和原始上传目录不直接暴露公网。

真实环境变量文件、密钥、证书和备份文件不得提交到 Git。提交模板文件时使用 `.env.example`。

## 文档维护

实现、重构、测试、部署配置或规则变化时，必须实时更新相关文档：

- `README.md`：项目总览、启动方式、目录结构和当前阶段。
- `PROJECT_PLAN.md`：架构、里程碑、部署方式、安全策略和协作规范。
- `PROJECT_PROGRESS.md`：已完成事项、进行中事项、风险、下一步和验证结果；每完成一个可验证任务后，必须明确写出紧接着要推进的下一个具体任务。
- `AGENT.md`：长期协作规则和硬性约束。

不要把临时方案写成最终方案；临时实现必须标明原因和后续处理。
