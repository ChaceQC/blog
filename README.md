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
        -> Redis
        -> Local Storage
```

生产环境只允许 Nginx 暴露 `80/443`。后端、MySQL、Redis 和原始上传目录都应位于内网或 Docker 私有网络中，不直接暴露公网。

## 功能模块

- 文章发布：Markdown 写作、LaTeX 公式、草稿、发布、定时发布、分类、标签、封面、摘要、SEO 信息、公开阅读页、分类/标签归档页、匿名浏览统计和点赞统计。
- 页面管理：关于、项目页等独立页面，支持后台维护和公开展示。
- 文件管理：图片和附件上传、MIME 与文件头校验、公开/私有文件、文章图片引用、短时签名访问、文章资源浏览器缓存复用、软删除和本地清理任务。
- 友链管理：友链分组、友链创建、公开申请、后台审核、排序、启用状态和定时健康检查。
- 小网站导航：按分组维护个人项目、工具站或自建服务入口，支持图标、标签、打开方式、公开导航页展示和点击统计。
- 站点设置：站点标题、描述、头像、首页碎念、社交入口等基础资料维护。
- 后台管理：管理员登录、HttpOnly Cookie 会话、CSRF、权限控制、操作日志、访问日志、登录日志和安全事件。
- 公开订阅与 SEO：RSS、sitemap、robots.txt、canonical、Open Graph、公开文章元信息和分类/标签稳定 URL。
- 遥测设计：基于 Project API Key 的服务端 metrics、events、logs 和 traces 上报契约，详见 `docs/telemetry-reporting-design.md`。
- 运维任务：过期加密会话清理、软删除文件物理清理、孤儿文件 dry-run 扫描和友链状态检查。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、uv。
- 前端：React、TypeScript、Vite、npm。
- 数据库：MySQL 8。
- 缓存、限流与一次性加密 salt：Redis；本地开发可回落内存后端。
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
  src/styles/         全局样式分层，index.css 只做聚合导入

deploy/               生产部署配置
  docker-compose.yml
  docker-compose.prod.yml
  nginx/
  env/
  scripts/
  systemd/

docs/                 架构、安全、遥测等专题设计文档

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

本地开发时前端 dev server 使用同源 `/api` 代理到 `config/development.json` 中的后端地址，保证应用层加密协商后前端可写入并随请求携带 `esid` Cookie。`esid` 按 `/api/public` 和 `/api/admin` 路径隔离，避免前台和后台切换时不同 scope 的加密会话互相覆盖；Cookie 本身保持小型稳定，每个加密 HTTP 请求还必须携带一次性 `X-Encryption-Esid-Salt` 供后端原子消费。

后台登录请求体不走普通明文 JSON，也不复用 `sensitive-v1` 的 AES-GCM 请求信封。前端会在后台加密会话协商返回的一次性 `login_challenge` 基础上使用 `Login Capsule v2`：对带固定分桶 padding 的用户名和密码载荷做 AES-CTR 加密，并用独立 HMAC 密钥绑定 session、challenge、请求方法、路径、时间戳、nonce 和密文；后端验证 `X-Encryption-Session`、`esid`、challenge、tag 和 nonce 后才解密登录载荷。

应用层加密使用 `/api/{scope}/encryption/salts` WebSocket 下发一次性动态 salt。WSS 帧本身会用 ECDH shared secret 派生 AES-GCM 包裹密钥加密，每帧还有随机 `wrap_salt`；salt lease 按用途分为 `esid`、`login_capsule`、`request` 和 `response`，只能消费一次。HTTP 请求会同时携带 `X-Encryption-Session`、`X-Encryption-Esid-Salt`、`X-Encryption-Response-Salt`，加密请求/登录 capsule 信封还会携带 `salt_id`；后端校验并消费 Redis 中的 lease 后才会继续处理。WSS 长连接使用同一加密帧格式传输应用层 `ping` / `pong` 心跳，前端连续丢失响应会关闭连接并按指数退避重连，重连期间不会降级回固定 salt；服务端对 WSS 消息按客户端 IP 和 `session_id` 做消息级限流，超过窗口后直接关闭连接。

前端创建加密请求头时会先建立 WSS salt 通道并批量获取当前请求需要的 `esid` 与 `response` lease，随后再生成并写入 `esid` Cookie，避免 `esid` 动态 chunk、WASM 或混淆后执行异常时阻断 WSS 启动。首屏多个公开查询并发时同一加密 session 只共享一个 salt WebSocket 创建过程，避免冷缓存下重复建连放大限流压力。

常用命令：

```powershell
cd frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

生产构建会先把 React、Query、KaTeX、图标等第三方依赖拆成 vendor chunk，再只对包含 `src/` 项目源码的 JavaScript chunk 做混淆，产物文件名使用纯 hash，避免从资源名识别业务模块；后台登录页和鉴权入口保留在初始包，后台工作区页面与后台 CRUD 接口代码只在登录校验通过后通过动态 import 加载。构建随后会为文本型静态资源生成 `.gz` 预压缩文件，Nginx 通过 `gzip_static` 优先传输压缩资源。混淆只提高前端算法阅读和复刻成本，后端仍以数据库中的加密会话 `key_material`、`X-Encryption-Session` 和 `esid` Cookie 校验作为安全边界。

### 联调约束

浏览器联调、接口联调或端到端验证结束后，关闭本次启动的前端、后端或预览服务，并确认 `15173`、`18080`、`14173` 等端口不再由本项目进程监听。

## 配置

后端本地配置来自 `backend/.env`，模板为 `backend/.env.example`。生产配置来自 `deploy/env/*.env`，模板为 `deploy/env/*.env.example`。

关键配置包括：

- `TZ`：后端容器时区，生产模板默认为 `Asia/Shanghai`，运行日志时间戳会按该时区显示。
- `BLOG_DATABASE_URL`：MySQL 连接串。
- `BLOG_SECRET_KEY`：应用密钥，生产必须使用强随机值。
- `BLOG_PUBLIC_BASE_URL`：公网 HTTPS 基础地址，用于生成 RSS、sitemap、robots.txt 和签名 URL。
- `BLOG_UPLOAD_ROOT`：上传文件存储目录。
- `BLOG_UPLOAD_MAX_SIZE_BYTES`：后端上传上限，默认 `20971520`，需与 Nginx `client_max_body_size 20m` 保持一致。
- `BLOG_AVATAR_CACHE_TTL_SECONDS`：公开首页头像和友链头像的本地缓存有效期，默认 `3600` 秒；过期后由下一次访问触发重新拉取。
- `BLOG_AVATAR_CACHE_MAX_SIZE_BYTES`：单个远程头像缓存拉取大小上限，默认 `2097152`。
- `BLOG_AVATAR_CACHE_REQUEST_TIMEOUT_SECONDS`：远程头像拉取超时时间，默认 `5` 秒。
- `BLOG_AVATAR_CACHE_RETRY_ATTEMPTS`：远程头像拉取失败后的重试次数，默认 `2`。
- `BLOG_RATE_LIMIT_BACKEND`：共享后端，支持 `memory` 和 `redis`；生产必须使用 `redis`，用于限流、访问日志去重和一次性加密 salt lease。
- `BLOG_REDIS_URL`：Redis 连接串，生产示例为 `redis://redis:6379/0`。
- `BLOG_ADMIN_ENCRYPTION_SESSION_ACTIVE_LIMIT_PER_IP`：后台加密会话单 IP 活跃数量上限，默认 `30`。
- `BLOG_PUBLIC_ENCRYPTION_SESSION_ACTIVE_LIMIT_PER_IP`：公开加密会话单 IP 活跃数量上限，默认 `60`。
- `BLOG_POST_INTERACTION_RATE_LIMIT_MAX_ATTEMPTS` / `BLOG_POST_INTERACTION_RATE_LIMIT_WINDOW_SECONDS`：公开文章浏览与点赞接口的 IP 级限流，默认 `30/60s`。
- `BLOG_POST_VIEW_DEDUPE_SECONDS`：同一匿名设备短时间重复访问同一文章的浏览计数去重窗口，默认 `600` 秒。
- `BLOG_POST_LIKE_RISK_WINDOW_SECONDS`：同一风险指纹对同一文章首次点赞的风控窗口，默认 `86400` 秒，用于提高无痕窗口刷赞成本。
- `BLOG_TELEMETRY_ENABLED`：遥测上报开关，默认 `false`；关闭时后端不会向摄入服务发送任何遥测请求。
- `BLOG_TELEMETRY_ENDPOINT`：遥测摄入服务地址，启用遥测时填写，例如 `https://telemetry.example.com` 或已包含 `/api/v1/ingest` 的地址。
- `BLOG_TELEMETRY_API_KEY`：遥测项目的 Project API Key，只能放在后端 `.env` 或生产 `backend.env`，不能写入前端配置、浏览器包、URL 或请求参数。
- `BLOG_TRUSTED_PROXY_HOSTS`：可信反向代理直连后端的 IP 或 CIDR 列表；只有这些来源的 `X-Forwarded-For` / `X-Real-IP` 会被用于应用层限流、数据库访问日志和后端运行日志。
- `BLOG_ACCESS_LOG_DEDUPE_SECONDS`：成功 `GET/HEAD` 访问日志短时去重窗口，默认 `60`；同一 IP 在窗口内重复访问同一 path 只写入第一条，错误和写操作仍逐条记录。

访问日志只保留类型、方法、path、状态码、实体类型/id、IP、UA 和时间，不保存 query、临时 token、签名参数、slug、文件名或 MIME 摘要；后台审计日志只保留动作、实体 id、操作者和最小状态/字段名摘要，不保存标题、URL、文件名、正文或完整设置值。应用层加密会话除 `X-Encryption-Session` 外还要求同源 `esid` Cookie：前端用 ECDH shared secret、`session_id`、scope 和过期时间生成可逆 sid，后端用数据库 `key_material` 逆运算并校验 HMAC、session、scope 和过期时间；每个 HTTP 请求还必须携带并消费一次性 `X-Encryption-Esid-Salt`，登录 capsule、加密请求和加密响应的 HKDF salt 也来自 WSS 加密下发的一次性 lease。生产后端容器通过项目启动入口把 `BLOG_TRUSTED_PROXY_HOSTS` 同步传给 Uvicorn，因此 `docker compose logs backend` 中的运行访问日志也会按可信代理头显示真实访客 IP，并带有时间戳；时间戳使用容器内 `TZ`/`tzdata` 配置，模板默认 `Asia/Shanghai`。后端镜像默认启用 UTF-8 环境变量，并使用腾讯云 Debian/PyPI/uv 镜像源，避免终端和 Python IO 出现中文编码漂移并加快国内构建。后端所有响应都会设置 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy` 和 `Permissions-Policy`；生产环境额外设置 HSTS 与 Content Security Policy，Nginx 仍保留同等安全响应头作为公网入口兜底。

遥测上报设计见 `docs/telemetry-reporting-design.md`。遥测摄入使用 Project API Key，不使用后台登录 token，也不由本项目传 `project_id`；第一阶段只允许后端、维护任务和部署脚本持有 API Key。当前实现通过后端 `.env` 控制是否上传，默认关闭；启用后会异步上报 HTTP 耗时/错误、限流、加密会话、公开文章互动、文件访问、后台审计、友链申请、导航跳转、维护任务和部署完成事件。上报前会使用路由模板和低基数字段，不上报正文、slug、完整 URL/query、签名 token、Cookie、加密材料、文件名、MIME、外部 URL 或完整设置值。

文章浏览和点赞使用版本化匿名设备指纹摘要，后端再结合可信代理 IP、UA 和语言头做 HMAC 派生，不保存原始高维指纹；点赞接口只接受目标布尔状态，不接受计数增减。文章软删除时会清理对应匿名点赞记录并重置展示计数，物理删除由外键级联兜底。

公开首页头像和友链头像会先通过后端签名缓存地址读取服务器本地缓存，前端再写入浏览器 Cache Storage；默认前后端都按 1 小时缓存窗口复用头像，减少访客浏览器直接触达原头像站点和重复请求。

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
npm.cmd test
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

该脚本需要本地后端和前端已启动，会覆盖后台加密登录、上传公开/私有图片、文章预览、创建发布文章、后台创建页面、公开文章和页面读取、分类/标签稳定路由、RSS、sitemap、robots.txt、前端 SEO 元信息、公开文件下载、后台私有文件下载、文件引用追踪、后台文章/文件列表分页、公开友链申请、后台友链分组与审核通过/拒绝、公开友链展示与拒绝项排除、小网站导航图标/标签/打开方式、公开跳转点击统计、`/links` 与 `/sites` 桌面和移动端页面检查，以及访问日志查询。默认会归档测试文章和页面、拒绝验证友链并隐藏验证导航数据。

公开页大数量分页与移动端溢出回归：

```powershell
cd backend
$env:PYTHONUTF8='1'
$env:BLOG_VERIFY_FRONTEND_URL='http://127.0.0.1:15173'
uv run python scripts/verify_public_page_pagination.py
```

该脚本同样需要本地后端和前端已启动，会在当前后端配置指向的运行库中写入带随机前缀的临时友链、站点目录和公开文件，使用 Playwright/Edge 检查 `/links?page=2`、`/sites?page=2`、`/files?page=2` 在桌面与移动端视口下的分页状态和横向溢出，并在结束时清理临时数据。浏览器通道可通过 `BLOG_VERIFY_BROWSER_CHANNEL` 调整，默认 `msedge`。

## 生产部署

生产目标环境为 Linux Debian。以下流程假设部署到 `/home/project/blog`，公网域名为 `blog.chacewebsite.cn`，宿主机已有证书 `/etc/nginx/ssl/blog.pem` 和 `/etc/nginx/ssl/blog.key`。

### 1. 准备系统依赖

安装 Git、curl 和 Docker Engine。Debian 软件源中的 `docker.io` 版本可能偏旧，建议按 Docker 官方仓库安装：

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git openssl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

确认 Docker 和 Compose plugin 可用：

```bash
docker --version
docker compose version
```

如果当前用户需要直接执行 Docker 命令：

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

### 2. 从 Git 拉取代码

空目录首次部署：

```bash
sudo mkdir -p /home/project/blog
sudo chown -R "$USER":"$USER" /home/project/blog
git clone https://github.com/ChaceQC/blog.git /home/project/blog
cd /home/project/blog
```

如果目录里已经是这个仓库，部署前先更新到远端最新版本：

```bash
cd /home/project/blog
git fetch origin
git pull --ff-only
```

### 3. 准备生产环境变量

```bash
cd /home/project/blog
cp deploy/env/backend.env.example deploy/env/backend.env
cp deploy/env/mysql.env.example deploy/env/mysql.env
cp deploy/env/nginx.env.example deploy/env/nginx.env
```

生成两个强密码或密钥：

```bash
openssl rand -hex 32
openssl rand -base64 32
```

编辑 `deploy/env/mysql.env`，至少替换这两项：

```dotenv
MYSQL_PASSWORD=替换为数据库业务用户密码
MYSQL_ROOT_PASSWORD=替换为数据库root密码
```

编辑 `deploy/env/backend.env`，关键项应与真实域名和 MySQL 密码一致：

```dotenv
BLOG_SECRET_KEY=替换为32位以上强随机值
BLOG_PUBLIC_BASE_URL=https://blog.chacewebsite.cn
BLOG_ALLOWED_HOSTS=["blog.chacewebsite.cn"]
BLOG_CORS_ORIGINS=["https://blog.chacewebsite.cn"]
BLOG_DATABASE_URL=mysql+aiomysql://blog_app:替换为数据库业务用户密码@mysql:3306/blog?charset=utf8mb4
BLOG_ADMIN_COOKIE_SECURE=true
BLOG_DEBUG=false
BLOG_DOCS_ENABLED=false
BLOG_RATE_LIMIT_BACKEND=redis
BLOG_REDIS_URL=redis://redis:6379/0
BLOG_TRUSTED_PROXY_HOSTS=["172.16.0.0/12"]
BLOG_UPLOAD_ROOT=/data/blog/uploads
BLOG_UPLOAD_MAX_SIZE_BYTES=20971520
BLOG_AVATAR_CACHE_TTL_SECONDS=3600
BLOG_AVATAR_CACHE_MAX_SIZE_BYTES=2097152
BLOG_AVATAR_CACHE_REQUEST_TIMEOUT_SECONDS=5
BLOG_AVATAR_CACHE_RETRY_ATTEMPTS=2
BLOG_ADMIN_ENCRYPTION_SESSION_ACTIVE_LIMIT_PER_IP=30
BLOG_PUBLIC_ENCRYPTION_SESSION_ACTIVE_LIMIT_PER_IP=60
BLOG_ACCESS_LOG_DEDUPE_SECONDS=60
```

`BLOG_DATABASE_URL` 应使用 `mysql+aiomysql://`。后端会临时兼容旧的 `mysql+asyncmy://` 前缀并在运行时映射到 `aiomysql`，但生产服务器的真实 `deploy/env/backend.env` 仍建议显式改为 `mysql+aiomysql://...`，避免继续依赖已命中 advisory 的旧驱动前缀。若使用宿主机 Nginx 反代到 Docker 后端，请把 `BLOG_TRUSTED_PROXY_HOSTS` 改成后端看到的宿主机/网关直连 IP 或 CIDR；如果日志里看到 `172.23.0.1` 这类 Docker 网关地址，通常可填 `["172.16.0.0/12"]`，或只填实际网关 IP。后端直接绑定并由宿主机回环访问时才填 `["127.0.0.1"]`。填错时功能仍可用，但应用层限流和访问日志会按代理 IP 而不是真实访客 IP 计数。

编辑 `deploy/env/nginx.env`：

```dotenv
BLOG_DOMAIN=blog.chacewebsite.cn
BLOG_SSL_CERTIFICATE=/etc/nginx/ssl/blog.pem
BLOG_SSL_CERTIFICATE_KEY=/etc/nginx/ssl/blog.key
```

### 4. 选择 Nginx 部署方式

如果使用 Compose 内置 Nginx，请继续按下文的 `deploy/docker-compose.local.yml` 挂载证书目录，并用包含 nginx 服务的 compose 命令启动。`deploy/docker-compose.local.yml` 是服务器本地文件，已被 `.gitignore` 忽略；如果前面已经创建过，请编辑合并内容，不要直接覆盖。

如果使用宿主机已有 Nginx，不启动 Compose 内置 Nginx 服务即可；宿主机 Nginx 仍需要把 `/api/` 反代到 `http://127.0.0.1:18080`，并把前端静态目录指向 `/var/www/blog`。上传文件目录不能配置为 Nginx 静态目录，公开文件和文章图片必须继续走后端签名接口。若需让宿主机访问后端容器，在服务器本地覆盖文件中加入：

```yaml
services:
  backend:
    ports:
      - "127.0.0.1:18080:8000"
```

此时后端容器看到的连接来源常是 Docker 网关地址，例如 `172.23.0.1`。为了让访问日志、登录日志和限流使用真实访客 IP，`deploy/env/backend.env` 里的 `BLOG_TRUSTED_PROXY_HOSTS` 应包含该网关 IP 或 Docker bridge CIDR，例如 `["172.16.0.0/12"]`。宿主机 Nginx 的站点配置也必须向后端传递代理头：

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

宿主机 Nginx 场景下，仍需单独构建 nginx 镜像来产出最新 React 静态文件，再复制到宿主机站点目录：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml build nginx
CID=$(docker create blog-nginx)
sudo rm -rf /var/www/blog/*
sudo docker cp "$CID":/usr/share/nginx/html/. /var/www/blog/
docker rm "$CID"
```

### 5. 挂载已有 SSL 证书

基础 Compose 文件默认只挂载项目内的 `deploy/certs/letsencrypt`，如果使用宿主机 `/etc/nginx/ssl` 中的现成证书，需要在 `deploy/docker-compose.local.yml` 中加入：

```yaml
services:
  nginx:
    volumes:
      - /etc/nginx/ssl:/etc/nginx/ssl:ro
```

确认宿主机证书文件存在且 Docker 可读：

```bash
sudo test -r /etc/nginx/ssl/blog.pem
sudo test -r /etc/nginx/ssl/blog.key
```

### 6. 准备数据目录

```bash
sudo mkdir -p /data/blog/uploads /data/blog/backups/mysql /data/blog/backups/uploads
```

后端容器以非 root 用户运行。首次启动后如果上传文件时报权限错误，按容器内实际 UID/GID 修正上传目录：

```bash
APP_UID=$(docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml exec -T backend id -u)
APP_GID=$(docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml exec -T backend id -g)
sudo chown -R "${APP_UID}:${APP_GID}" /data/blog/uploads
```

### 7. 构建并启动服务

先展开检查 Compose 配置：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml config --quiet
```

启动服务：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml up -d --build
```

宿主机 Nginx 场景只启动后端、MySQL 和 Redis：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml up -d --build backend mysql redis
```

查看状态和日志：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml ps
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml logs -f nginx backend
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml logs --tail=200 --timestamps backend
```

后端运行访问日志由生产启动入口读取 `BLOG_TRUSTED_PROXY_HOSTS` 后交给 Uvicorn 处理；时间戳按容器内 `TZ` 显示，模板默认 `Asia/Shanghai`。如果日志里仍看到 `172.23.0.1` 这类 Docker 网关地址，先确认服务器真实 `deploy/env/backend.env` 已包含后端看到的代理 IP/CIDR，并重新构建 backend 镜像。

### 8. 初始化数据库

后端镜像包含 `uv`、Alembic 和应用代码，迁移应在后端容器内执行：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml exec -T backend uv run alembic upgrade head
```

创建后台管理员。省略 `--password` 时会交互输入，生产环境不要把密码写进 shell 历史：

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml exec backend uv run python -m app.cli create-admin --username admin --email admin@example.com --display-name 管理员
```

### 9. 验证公网入口

FastAPI 路由主要是 GET，不要对 API 全部使用 `curl -I`。按下面检查：

```bash
curl -I https://blog.chacewebsite.cn/
curl -fsS https://blog.chacewebsite.cn/api/public/status
curl -fsS https://blog.chacewebsite.cn/rss.xml | head
curl -fsS https://blog.chacewebsite.cn/sitemap.xml | head
curl -fsS https://blog.chacewebsite.cn/robots.txt
```

公网防火墙或安全组只放行 `80/tcp` 和 `443/tcp`。MySQL `3306`、Redis `6379` 和后端 `8000` 只在 Docker 内部网络访问，不要映射到公网。

### 9. 后续更新

每次部署新版本：

```bash
cd /home/project/blog
git fetch origin
git pull --ff-only
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml up -d --build
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml exec -T backend uv run alembic upgrade head
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml -f deploy/docker-compose.local.yml ps
```

## 运维任务

后台维护任务通过 CLI 执行，不开放公开 HTTP 入口。

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-encryption-sessions
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-deleted-files --older-than-days 7 --limit 100
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-orphan-files --limit 1000
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli check-friend-links --limit 100 --timeout-seconds 5
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml exec -T backend uv run python -m app.cli cleanup-logs --access-days 30 --audit-days 180 --login-days 180 --security-days 180 --limit 5000
```

`cleanup-orphan-files` 默认只 dry-run。确认输出后，才可显式追加 `--delete` 删除孤儿文件。`cleanup-logs` 默认保留 30 天访问日志、180 天审计/登录/安全事件日志；某类天数传 `0` 可跳过对应表。

systemd timer 示例位于 `deploy/systemd/`，默认假设项目路径为 `/opt/blog`：

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blog-cleanup-encryption-sessions.timer
sudo systemctl enable --now blog-cleanup-deleted-files.timer
sudo systemctl enable --now blog-cleanup-logs.timer
sudo systemctl enable --now blog-scan-orphan-files.timer
sudo systemctl enable --now blog-check-friend-links.timer
systemctl list-timers 'blog-*'
```

## 备份与恢复

脚本位于 `deploy/scripts/`：

- `backup_mysql.sh`：备份 MySQL。
- `upgrade_backend_db.sh`：默认先备份 MySQL、构建 backend 镜像，再用一次性后端容器执行 Alembic 数据库迁移。
- `restore_mysql.sh`：恢复 MySQL。
- `backup_uploads.sh`：备份上传文件目录。
- `restore_uploads.sh`：恢复上传文件目录，会覆盖同名文件但不会删除现有额外文件。
- `renew_cert.sh`：证书续期示例。

```bash
bash deploy/scripts/backup_mysql.sh
bash deploy/scripts/upgrade_backend_db.sh
bash deploy/scripts/backup_uploads.sh
bash deploy/scripts/restore_mysql.sh /data/blog/backups/mysql/blog-YYYYMMDDTHHMMSSZ.sql.gz
CONFIRM_RESTORE_UPLOADS=yes bash deploy/scripts/restore_uploads.sh /data/blog/backups/uploads/uploads-YYYYMMDDTHHMMSSZ.tar.gz
```

宿主机 Nginx 场景可通过 `COMPOSE_EXTRA_FILES` 让 MySQL 备份、恢复和迁移脚本复用同一份本地 Compose 覆盖：

```bash
COMPOSE_EXTRA_FILES=deploy/docker-compose.local.yml bash deploy/scripts/upgrade_backend_db.sh
```

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
