# 前端工程

本目录是个人博客系统的 React + TypeScript + Vite 前端工程。

## 本地开发

开发环境默认为 Windows 11，终端和文件读写统一使用 UTF-8。

```powershell
npm install
npm run dev
npm run lint
npm run build
```

## 目录约定

- `src/app`：应用入口、路由和全局客户端。
- `src/routes/public`：前台公开页面。
- `src/routes/admin`：后台管理页面。
- `src/features`：按业务模块拆分文章、文件、友链、导航和设置。
- `src/api`：接口客户端与请求封装。
- `src/components`：跨模块复用组件。

## 文案规范

界面文案、维护说明和代码注释默认使用中文。命令、变量名、第三方包名、API 字段和行业通用术语可以保留英文。
