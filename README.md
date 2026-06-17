# 个人博客系统

自托管个人博客与轻量 CMS。系统面向公网部署设计，包含文章发布、页面管理、文件管理、友链、小网站导航、后台管理、公开订阅和基础运维任务。

## 从 Git 开始

项目使用 Git 和 GitHub 管理，默认远端为 `origin`，默认主分支为 `main`，日常开发在 `dev` 分支进行。

首次获取代码：

```powershell
git clone https://github.com/ChaceQC/blog.git
cd blog
git switch dev
git status --short --branch
```

开始开发前先同步远端：

```powershell
git fetch origin
git switch dev
git pull --ff-only origin dev
```

提交前检查工作区，确认只包含本次任务相关文件：

```powershell
git status --short --branch
git diff --check
```

完成一个可验证小步后提交并推送：

```powershell
git add <本次修改的文件>
git commit -m "docs: 中文说明"
git push origin dev
```

一个完整功能在 `dev` 验证通过后，再将 `main` 快进到 `dev`：

```powershell
git switch main
git merge --ff-only dev
git push origin main
git switch dev
```

## 架构概览

```text
Internet
  -> Nginx 80/443
    -> React 静态资源
    -> FastAPI Public API
    -> FastAPI Admin API
        -> Service Layer
        -> Repository Layer
        -> MySQL 8
        -> Redis 可选
        -> Local Storage
```

生产环境只允许 Nginx 暴露 `80/443`。后端、MySQL、Redis 和原始上传目录都应位于内网或 Docker 私有网络中，不直接暴露公网。

## 功能模块

- 文章发布：Markdown 写作、LaTeX 公式、草稿、发布、定时发布、分类、标签、封面、摘要、SEO 信息、公开阅读页和分类/标签归档页。
- 页面管理：关于、项目页等独立页面，支持后台维护和公开展示。
- 文件管理：图片和附件上传、MIME 与文件头校验、公开/私有文件、文章图片引用、短时签名访问、软删除和本地清理任务。
- 友链管理：友链创建、公开申请、后台审核、排序、启用状态和定时健康检查。
- 小网站导航：按分组维护个人项目、工具站或自建服务入口，支持公开导航页展示。
- 站点设置：站点标题、描述、头像、首页碎念、社交入口等基础资料维护。
- 后台管理：管理员登录、HttpOnly Cookie 会话、CSRF、权限控制、操作日志、访问日志、登录日志和安全事件。
- 公开订阅与 SEO：RSS、sitemap、robots.txt、canonical、Open Graph、公开文章元信息和分类/标签稳定 URL。
- 运维任务：过期加密会话清理、软删除文件物理清理、孤儿文件 dry-run 扫描和友链状态检查。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、uv。
- 前端：React、TypeScript、Vite、npm。
- 数据库：MySQL 8。
- 缓存与限流：Redis 可选，本地默认内存后端。
- 部署：Linux Debian、Docker Compose、Nginx、Let's Encrypt 或云厂商证书。
- 开发环境：Windows 11，文件读写和终端统一使用 UTF-8。

## 目录结构

```text
backend/              FastAPI 后端工程
  app/api/            Public API 与 Admin API
  app/services/       业务用例和领域规则
  app/repositories/   数据库访问
  app/models/         SQLAlchemy 模型
  app/schemas/        Pydantic DTO
  app/core/           配置、数据库、认证、日志、安全基础设施
  app/tasks/          后台维护任务
  migrations/         Alembic 迁移
  tests/              后端测试

frontend/             React 前端工程
  src/app/            路由和应用入口
  src/routes/         前台和后台页面
  src/features/       posts、files、links、sites、settings 等业务模块
  src/api/            请求客户端和加密 API 封装

deploy/               生产部署配置
  docker-compose.yml
  docker-compose.prod.yml
  nginx/
  env/
  scripts/
  systemd/

AGENT.md              开发协作规则
PROJECT_PLAN.md       项目计划书和架构设计
PROJECT_PROGRESS.md   实现进度、验证记录和下一步
```

## 本地开发

本地开发避免使用常见端口。前端默认 `15173`，前端预览默认 `14173`，后端默认 `18080`。端口、数据库连接、CORS、Trusted Host、上传目录和 API 地址都必须来自配置文件或环境变量。

### 后端

```powershell
cd backend
uv sync
Copy-Item .env.example .env
$env:PYTHONUTF8='1'
uv run python main.py
```

后端本地启动必须在 `backend` 目录使用 `uv run python main.py`，不要直接使用系统 Python 或全局 Python。

常用命令：

```powershell
cd backend
$env:PYTHONUTF8='1'
uv run ruff check .
uv run pytest
uv run alembic upgrade head --sql
uv run python -m app.cli --help
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

常用命令：

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

### 联调约束

浏览器联调、接口联调或端到端验证结束后，关闭本次启动的前端、后端或预览服务，并确认 `15173`、`18080`、`14173` 等端口不再由本项目进程监听。

## 配置

后端本地配置来自 `backend/.env`，模板为 `backend/.env.example`。生产配置来自 `deploy/env/*.env`，模板为 `deploy/env/*.env.example`。

关键配置包括：

- `BLOG_DATABASE_URL`：MySQL 连接串。
- `BLOG_SECRET_KEY`：应用密钥，生产必须使用强随机值。
- `BLOG_PUBLIC_BASE_URL`：公网 HTTPS 基础地址，用于生成 RSS、sitemap、robots.txt 和签名 URL。
- `BLOG_UPLOAD_ROOT`：上传文件存储目录。
- `BLOG_RATE_LIMIT_BACKEND`：限流后端，支持 `memory` 和 `redis`。
- `BLOG_REDIS_URL`：Redis 连接串，生产示例为 `redis://redis:6379/0`。

真实 `.env`、密钥、证书私钥、备份文件和上传文件不得提交到 Git。

## 数据库迁移

迁移由 Alembic 管理。连接真实数据库前先确认 `BLOG_DATABASE_URL` 指向目标库。

```powershell
cd backend
$env:PYTHONUTF8='1'
uv run alembic upgrade head
```

开发验证建议使用临时库，例如 `blog_codex_migration_test`。验证完成后再删除临时库，避免污染真实运行数据。

## 初始管理员

数据库迁移完成后创建初始后台管理员：

```powershell
cd backend
$env:PYTHONUTF8='1'
uv run python -m app.cli create-admin --username admin --email admin@example.com --display-name 管理员
```

省略 `--password` 时会交互式输入密码。生产环境不要把密码写入命令历史。

## 验证

后端基础验证：

```powershell
cd backend
$env:PYTHONUTF8='1'
uv run ruff check .
uv run pytest
```

前端基础验证：

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

部署配置验证：

```powershell
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config --quiet
```

真实运行库 HTTP 闭环验证：

```powershell
cd backend
$env:PYTHONUTF8='1'
$env:BLOG_VERIFY_ADMIN_USERNAME='admin'
$env:BLOG_VERIFY_ADMIN_PASSWORD='你的本地后台管理员密码'
$env:BLOG_VERIFY_FRONTEND_URL='http://127.0.0.1:15173'
uv run python scripts/verify_runtime_publish_flow.py
```

该脚本需要本地后端和前端已启动，会覆盖后台加密登录、上传公开/私有图片、文章预览、创建发布文章、后台创建页面、公开文章和页面读取、分类/标签稳定路由、RSS、sitemap、robots.txt、前端 SEO 元信息、公开文件下载、后台私有文件下载、文件引用追踪、后台文章/文件列表分页和访问日志查询。默认会归档测试文章和页面。

公开页大数量分页与移动端溢出回归：

```powershell
cd backend
$env:PYTHONUTF8='1'
$env:BLOG_VERIFY_FRONTEND_URL='http://127.0.0.1:15173'
uv run python scripts/verify_public_page_pagination.py
```

该脚本同样需要本地后端和前端已启动，会在当前后端配置指向的运行库中写入带随机前缀的临时友链、站点目录和公开文件，使用 Playwright/Edge 检查 `/links?page=2`、`/sites?page=2`、`/files?page=2` 在桌面与移动端视口下的分页状态和横向溢出，并在结束时清理临时数据。浏览器通道可通过 `BLOG_VERIFY_BROWSER_CHANNEL` 调整，默认 `msedge`。

## 生产部署

生产目标环境为 Linux Debian。推荐部署目录为 `/opt/blog`，以下命令假设代码已位于该目录。

### 1. 准备环境

安装 Docker Engine、Docker Compose plugin、Git 和基础工具：

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git
```

按 Docker 官方文档安装 Docker Engine 后，确认：

```bash
docker --version
docker compose version
```

### 2. 准备配置

```bash
cd /opt/blog
cp deploy/env/backend.env.example deploy/env/backend.env
cp deploy/env/mysql.env.example deploy/env/mysql.env
cp deploy/env/nginx.env.example deploy/env/nginx.env
```

至少修改以下内容：

- `deploy/env/backend.env`：`BLOG_SECRET_KEY`、`BLOG_DATABASE_URL`、`BLOG_PUBLIC_BASE_URL`、CORS、Trusted Host、Cookie 安全配置、上传目录、Redis 配置。
- `deploy/env/mysql.env`：MySQL root 密码、业务库、业务账号和密码。
- `deploy/env/nginx.env`：域名、证书路径和反向代理相关配置。

生产 `BLOG_PUBLIC_BASE_URL` 必须使用公网 HTTPS 地址，例如 `https://example.com`。

### 3. 启动服务

```bash
cd /opt/blog
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

查看状态：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml ps
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml logs -f backend
```

### 4. 执行迁移

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run alembic upgrade head
```

### 5. 创建管理员

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec backend uv run python -m app.cli create-admin --username admin --email admin@example.com --display-name 管理员
```

### 6. 检查公网入口

确认以下地址返回正常：

```bash
curl -I https://example.com/
curl -I https://example.com/api/public/status
curl -I https://example.com/rss.xml
curl -I https://example.com/sitemap.xml
curl https://example.com/robots.txt
```

公网安全组只放行 `80/tcp` 和 `443/tcp`。不要将 MySQL `3306`、Redis `6379` 或后端内部端口暴露到公网。

## 运维任务

后台维护任务通过 CLI 执行，不开放公开 HTTP 入口。

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-encryption-sessions
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-deleted-files --older-than-days 7 --limit 100
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-orphan-files --limit 1000
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli check-friend-links --limit 100 --timeout-seconds 5
```

`cleanup-orphan-files` 默认只 dry-run。确认输出后，才可显式追加 `--delete` 删除孤儿文件。

systemd timer 示例位于 `deploy/systemd/`，默认假设项目路径为 `/opt/blog`：

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blog-cleanup-encryption-sessions.timer
sudo systemctl enable --now blog-cleanup-deleted-files.timer
sudo systemctl enable --now blog-scan-orphan-files.timer
sudo systemctl enable --now blog-check-friend-links.timer
systemctl list-timers 'blog-*'
```

## 备份与恢复

脚本位于 `deploy/scripts/`：

- `backup_mysql.sh`：备份 MySQL。
- `restore_mysql.sh`：恢复 MySQL。
- `renew_cert.sh`：证书续期示例。

生产环境至少需要备份：

- MySQL 数据库。
- `BLOG_UPLOAD_ROOT` 对应的上传文件目录。
- 生产环境变量、证书和部署版本信息。

备份文件应加密保存到服务器外部位置，并定期做恢复演练。

## 文档分工

- `README.md`：开发者入口、架构、本地开发、验证和部署说明。
- `PROJECT_PLAN.md`：项目计划、里程碑、架构原则和长期设计。
- `PROJECT_PROGRESS.md`：每次实现、重构、测试和部署调整的进度记录。
- `AGENT.md`：协作规则和硬性约束。
