# 项目进度

## 2026-06-15

### 已完成

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
- 前端登录态启动时会调用当前用户接口校验本地 Access Token，失效 session 会自动清理。

### 进行中

- M1 认证与后台框架正在推进，后台登录和当前用户校验闭环已覆盖后端接口、初始管理员创建命令和前端登录态保护。

### 阻塞与风险

- 待确认真实域名、服务器环境、证书申请方式和对象存储选择。
- 真实 MySQL 验证已在临时库完成；生产数据库迁移仍需在正式环境备份后执行。
- 当前前端会话保存在 `localStorage`，后续如改为 Cookie 会话，需要补充 CSRF 防护策略。
- 后台接口已具备登录、当前用户、刷新和退出，仍需补充权限校验依赖和后台菜单权限状态。

### 下一步

- 接入菜单权限状态和更细的后台路由保护。
- 继续补充认证审计日志查询、基础限流和文章、文件、设置的最小 CRUD。

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
