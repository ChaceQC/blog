# 前端工程

本目录是个人博客系统的 React + TypeScript + Vite 前端工程。

前台 UI 采用 Innei/Yohaku 风格重新设计，依赖 `@yohaku/design-system` 作为设计 token 契约参考。当前工程未接入 Tailwind v4，因此运行时 CSS 在 `src/index.css` 中镜像 Yohaku 的 Pure 中性色、梅色 accent、serif 标题、纸面背景、细分隔线、轻玻璃和底部浮动导航，而不是直接导入包内 `@theme` CSS。

## 本地开发

开发环境默认为 Windows 11，终端和文件读写统一使用 UTF-8。本地开发避免使用常见端口，前端默认端口为 `15173`，预览默认端口为 `14173`。

```powershell
npm install
npm run dev
npm run lint
npm run build
```

本地开发端口、预览端口和 API 地址来自 `config/development.json`，不要写死在启动脚本或业务代码里。

## 目录约定

- `src/app`：应用入口、路由和全局客户端。
- `src/routes/public`：前台公开页面。
- `src/routes/admin`：后台管理页面。
- `src/features`：按业务模块拆分文章、文件、友链、导航和设置。
- `src/features/auth`：后台登录、会话保存和退出逻辑。
- `src/api`：接口客户端与请求封装。
- `src/components`：跨模块复用组件。

## UI 约定

- 前台公开页保持 Yohaku 式个人站体验：大留白、低对比文字、serif 中文标题、雨线纸面背景、底部浮动导航和细线列表。
- `/`、`/posts`、`/links`、`/sites` 必须共享同一套标题层级、列表密度和状态标签样式。
- 后台登录与工作台沿用同一套 token，但优先保证管理界面的可读性和操作效率。
- 不直接在业务组件中写原始色值；新增颜色应先映射到 `src/index.css` 的 Yohaku token 变量。

## 文案规范

界面文案、维护说明和代码注释默认使用中文。命令、变量名、第三方包名、API 字段和行业通用术语可以保留英文。
