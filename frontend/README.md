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
- `src/features/seo`：公开页面标题、description、canonical 和 Open Graph 元信息维护。
- `src/api`：接口客户端与请求封装。
- `src/components`：跨模块复用组件。

## UI 约定

- 前台公开页保持 Yohaku 式个人站体验：大留白、低对比文字、serif 中文标题、雨线纸面背景、底部浮动导航和细线列表。
- `/`、`/posts`、`/links`、`/sites` 必须共享同一套标题层级、列表密度和状态标签样式。
- `/categories/:slug` 与 `/tags/:slug` 复用文章归档视图，作为分类和标签的稳定公开 URL；归档筛选入口应优先链接到这两类路径。
- 后台登录与工作台沿用同一套 token，但优先保证管理界面的可读性和操作效率。
- 不直接在业务组件中写原始色值；新增颜色应先映射到 `src/index.css` 的 Yohaku token 变量。
- 公开首页、公开布局品牌、后台布局品牌和页面标题优先读取 `/api/public/settings/site-profile` 的真实站点资料，不再回退到演示站点文案。
- 首页社交入口使用统一细线图标展示，后台站点资料页可增删社交入口；新增入口应保持图标尺寸、颜色和邮箱入口一致。
- 公开文章、友链、站点目录和文件列表分页依赖接口返回的真实 `total`，页面应直接显示总页数，不再用多取一条记录判断下一页。
- 公开页面通过 `usePageSeo` 维护页面标题、description、canonical 和基础 `og:*`；新增公开页面时必须同步补齐可分享标题和描述。
- 日志类页面必须使用内部滚动列表或分页，不能让大量日志把整个后台页面无限撑长。

## 内容与文件约定

- 后台文章编辑器预览必须调用 `POST /api/admin/posts/preview`，随当前表单内容防抖刷新，不要求先保存文章。
- 文章 Markdown 中图片使用 `![说明](/api/public/posts/{slug}/files/{file_id}/render)` 稳定引用；前端不要把上传目录、对象 key 或临时下载链接直接写入正文。
- 后台文件详情的“复制文章引用”用于生成正文图片语法；公开文件栏下载按钮才使用当前会话生成的短时下载链接。
- 渲染后端返回的 HTML 时，`MathHtml` 负责把 `/api/...` 资源地址转换到配置中的后端 API 地址，并交给 KaTeX 渲染公式节点。

## 文案规范

界面文案、维护说明和代码注释默认使用中文。命令、变量名、第三方包名、API 字段和行业通用术语可以保留英文。
