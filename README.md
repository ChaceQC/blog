# 个人博客系统

这是一个自托管个人博客与轻量 CMS 项目。系统面向公网部署设计，包含文章发布、文件管理、友链、小网站导航和后台管理能力。

## 当前阶段

当前版本处于 `v0.1.0` 脚手架阶段，开发分支为 `dev`。M0 脚手架、生产部署骨架和初始 Alembic 迁移已完成，M1 已开始落地后台登录接口、初始管理员创建命令和前端登录页。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、uv。
- 前端：React、TypeScript、Vite、npm。
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

## 验证命令

后端：

```powershell
cd backend
uv run ruff check .
uv run pytest
$env:PYTHONUTF8='1'
uv run alembic upgrade head --sql
uv run alembic downgrade 20260615_0001:base --sql
uv run python -m app.cli --help
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

## 部署边界

生产部署目标为 Linux Debian。公网只允许 Nginx 暴露 `80/443`，后端、MySQL、Redis 和原始上传目录不直接暴露公网。

真实环境变量文件、密钥、证书和备份文件不得提交到 Git。提交模板文件时使用 `.env.example`。

## 文档维护

实现、重构、测试、部署配置或规则变化时，必须实时更新相关文档：

- `README.md`：项目总览、启动方式、目录结构和当前阶段。
- `PROJECT_PLAN.md`：架构、里程碑、部署方式、安全策略和协作规范。
- `PROJECT_PROGRESS.md`：已完成事项、进行中事项、风险、下一步和验证结果。
- `AGENT.md`：长期协作规则和硬性约束。

不要把临时方案写成最终方案；临时实现必须标明原因和后续处理。
