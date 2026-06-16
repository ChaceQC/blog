# 项目进度

## 2026-06-17

### 已完成

- 按用户要求将首页“近期笔墨”限制为最多 3 篇。
- 文章列表页改为每页 5 篇，超过 5 篇时显示上一页/下一页分页控件。
- 首页“碎念”已并入 `site_profile.musings`，后台“站点资料”页可编辑两条碎念内容和日期。
- 首页社交入口已并入 `site_profile.social_links`，后台“站点资料”页可编辑入口名称和 URL。
- 新增前端默认文章封面 `frontend/public/default-cover.svg`，无封面文章在列表和详情页都会加载默认封面，保持文章列表对齐。
- 新增后台图片缩略图接口 `/api/admin/files/{file_id}/thumbnail`，使用 Pillow 按需生成并缓存 360px 缩略图，封面选择器只加载缩略图，避免在后台列表中传输原图。
- 优化后台文章封面选择器：增加文件名搜索、每页 8 张分页和缩略图预览，避免图片数量变多后产生过长选项列表。
- 新增公开文章图片缩略图接口 `/api/public/posts/{slug}/files/{file_id}/thumbnail`，公开文章列表和详情页的封面 URL 改为带签名的缩略图地址，避免公开页加载封面原图。
- 参考 `https://innei.in/` 调整公开展示：顶部悬浮导航、首页身份区进入动效、近期笔墨细线时间线、碎念/来信轻分隔、横向“笔耕不辍”写作轨迹、雨线背景微动和列表 hover 位移。
- 将默认上传大小上限从 10MB 调整为 30MB，同步后端配置默认值、开发/部署环境示例和后台上传页提示；前端上传前会先拦截超过 30MB 的文件并显示中文提示。
- 修复公开文章列表与详情的阅读时长统计口径：后端 `count_words` 改为同时统计中文字符和英文/数字词，公开文章响应会用正文实时统计兜底旧数据，避免历史 `word_count` 偏小导致页面一直显示 `1 分钟`。
- 公开文章列表与详情响应新增 `cover_file_id` 与带签名的 `cover_image_url`，文章图片渲染接口允许公开文章封面文件走同一签名渲染路径。
- 前台 `/posts` 与 `/posts/:slug` 已展示文章封面，保留无封面文章的原列表布局。
- 后台 `/admin/posts` 已将封面文件 ID 输入升级为封面选择器，直接从后台公开图片文件中选择封面，不再要求手动粘贴文件 ID。
- 同步更新根目录 `README.md` 和 `PROJECT_PLAN.md`，记录封面选择器、前台封面展示和后续计划调整。
- 修复新建文章未设置封面时仍发送 `cover_file_id: null` 的问题；前端写入 payload 现在只在封面文件 ID 非空时发送 `cover_file_id`，避免兼容旧后端进程或额外字段校验导致 `invalid encrypted request payload`。
- 保持后端加密请求体校验失败的响应为泛化错误，不向浏览器暴露字段级校验细节。
- 已停止昨晚仍在监听 `18080` 的旧后端进程，并使用项目虚拟环境 `uv run python main.py` 重启后端；当前 `/healthz` 返回 200。
- 按用户要求更新 `AGENT.md`、`README.md`、`backend/README.md` 和 `PROJECT_PLAN.md`：后端本地启动必须使用 `uv run python main.py`，联调或验证结束后必须关闭本次启动的本项目服务，并确认相关端口不再监听。
- 本次验证后已关闭当前监听 `18080` 的后端服务和监听 `15173` 的前端服务，确认 `18080`、`15173`、`14173` 均无监听。
- 按用户要求将“列表过度平铺、移动端适配混乱、后台页面持续向后堆积”写入 `PROJECT_PLAN.md` 和本进度的下一步。
- 新增通用分页控件 `ListPager`，公开文章列表、友链、站点目录、公开文件和后台文章、页面、文件、友链、导航、日志列表开始复用分页浏览，避免数据变多后整页平铺。
- 后台站点资料页改为“基础资料 / 首页碎念 / 社交入口”标签分区，减少新增字段直接堆到页面底部的问题。
- 补充移动端布局修正：全局禁止横向溢出，公开导航和后台标签栏可横向滚动，后台列表项和分页按钮在窄屏下改为单列显示。
- 修复移动端公开文章列表封面过大的问题：小屏文章行改为编号、小封面和正文三列紧凑布局，并限制摘要行数；同时提高公开页移动端顶部留白并补充返回文章列表按钮样式，避免固定导航遮挡。
- 优化公开页移动端整体安全边距，`public-shell` 与顶部导航统一使用更宽的左右留白，极窄屏再降级，避免内容贴紧屏幕边缘。
- 后台登录页新增“返回主站点”入口，避免未登录时只能停留在后台登录界面。
- 修复后台移动端总览等页面右侧溢出问题：后台 shell 在小屏加入统一安全边距，侧栏、主内容、面板和指标卡增加 `min-width: 0`，避免卡片和网格撑出屏幕。
- 修复后台总览“最近素材”内部溢出：标题行、文件列表、文件行和长文件路径增加收缩与换行约束，避免长文件名或 object key 撑出面板。
- 新增后台维护任务入口 `backend/app/tasks/encryption.py`，提供过期应用层加密会话清理能力，后续文件物理清理、孤儿文件清理、友链健康检查和 sitemap 刷新可沿用同一类任务入口。
- 新增 CLI 子命令 `uv run python -m app.cli cleanup-encryption-sessions`，可由人工、cron 或 systemd timer 调用，清理 `encryption_sessions` 中已过期的短期会话并输出清理数量。
- `EncryptionSessionManager` 新增 `cleanup_expired_sessions` 业务方法，只有确实删除过期记录时才提交事务，避免空清理产生无意义提交。
- 补充加密会话清理测试，覆盖“只删除过期会话并提交”和“没有过期会话不空提交”。
- 按用户要求更新 `AGENT.md`、`README.md`、`backend/README.md` 和 `PROJECT_PLAN.md`：每完成一个可验证任务后，必须在进度记录中写清楚紧接着要推进的下一个具体任务。
- 新增后台文件下载接口 `GET /api/admin/files/{file_id}/download`，登录且具备 `file:upload` 权限的后台用户可以下载公开或私有 active 文件，文件仍从后端读取，不暴露原始上传目录。
- `FileService` 新增 `prepare_admin_download` 用例，复用存储路径安全解析，允许读取私有 object key 但仍限制路径必须位于 `BLOG_UPLOAD_ROOT` 内。
- 后台文件下载会写入 `access_logs`，成功记录文件名和 MIME，文件不存在或不可下载时记录对应 404/403。
- 前端后台文件详情新增“下载”按钮，直接打开后台鉴权下载接口；公开短时链接仍只用于公开文件分享，私有文件不生成公开链接。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，标记私有文件后台鉴权下载已完成，并将下一步调整为软删除文件物理清理任务。
- 新增软删除文件物理清理任务 `cleanup_deleted_files` 和 CLI 子命令 `uv run python -m app.cli cleanup-deleted-files --older-than-days 7 --limit 100`，默认保留 7 天，单次最多扫描 100 条。
- 文件清理任务只处理 `status=deleted`、`deleted_at` 早于保留时间且没有 `file_usages` 引用的文件；路径解析必须保持在 `BLOG_UPLOAD_ROOT` 内，否则跳过。
- 清理任务会删除本地物理文件和对应缩略图；若物理文件已缺失，会清理数据库软删记录并计入缺失文件数量；若仍有引用或路径不安全则跳过且不提交删除。
- 文件 Repository 补充软删除清理候选查询和记录删除方法，`FileService` 返回扫描数、删除记录数、删除物理文件数、缺失物理文件数和跳过数，CLI 会输出汇总。
- 补充软删除文件清理测试，覆盖正常删除物理文件与缩略图、物理文件缺失时清理记录、仍有引用或路径不安全时跳过。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，标记软删除文件物理清理任务已完成，并将下一步调整为孤儿文件清理任务。
- 新增孤儿文件清理任务 `cleanup_orphan_files` 和 CLI 子命令 `uv run python -m app.cli cleanup-orphan-files --limit 1000`，默认 dry-run，只汇总扫描结果和孤儿文件示例。
- 孤儿文件任务只扫描 `BLOG_UPLOAD_ROOT` 下 `public` 与 `private` 托管目录，跳过 `.thumbs` 和其他非托管目录；对没有 active/deleted 数据库记录的文件，只有显式传入 `--delete` 才会删除。
- 文件 Repository 补充 active/deleted object key 查询，`FileService` 返回扫描文件数、已登记文件数、孤儿文件数、删除数、跳过数和孤儿 object key 示例。
- 补充孤儿文件清理测试，覆盖 dry-run 不删除、显式删除仅处理非登记托管文件、扫描上限生效。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，标记孤儿文件清理任务已完成，并将下一步调整为真实 MySQL 临时库与临时上传目录闭环验证。

### 进行中

- M1 内容管理继续推进，文章封面选择与前台展示已形成第一版闭环；软删除文件物理清理和孤儿文件清理任务已接入，下一步切到真实 MySQL 临时库与临时上传目录闭环验证。

### 阻塞与风险

- 若前端页面仍保留旧 bundle 或旧 dev server 状态，需刷新页面后再保存文章；后端已重启到当前代码。
- 实际执行 `cleanup-encryption-sessions` 会删除当前配置数据库里的过期会话记录；本次仅验证 CLI 子命令可见性和业务方法测试，未在未确认目标库的情况下直接运行清理命令。
- 后台文件下载接口返回文件流，不走 `content-v1` 加密信封；安全边界依赖后台 HttpOnly Cookie 或 Bearer Token 鉴权、`file:upload` 权限和后端路径校验。
- 实际执行 `cleanup-deleted-files` 会删除当前配置数据库中的软删记录和本地物理文件；本次只跑服务层单元测试和 CLI 可见性检查，未在未确认目标库与上传目录的情况下直接运行清理命令。
- `cleanup-orphan-files` 默认 dry-run 不删除文件；显式加 `--delete` 会删除当前配置上传目录中的孤儿文件，本次未在未确认目标库与上传目录的情况下执行真实删除。

### 下一步

- 补充真实 MySQL 临时库和临时上传目录验证，确认上传、软删除、`cleanup-deleted-files`、`cleanup-orphan-files` dry-run 与显式删除可以串成闭环。
- 文件清理闭环验证完成后，再评估 Redis 共享限流适配器，替换或扩展当前单进程内存限流器。
- 使用真实 MySQL 运行库验证上传图片、选择封面、发布文章、前台封面展示、正文图片渲染、公开文件栏下载和后台访问日志查询。

### 验证

- 已运行 `uv run ruff check .`，通过。
- 已运行 `uv run pytest tests\test_markdown_provider.py tests\test_public_content_api.py tests\test_admin_files_api.py tests\test_content_service.py`，29 个测试通过；仍存在 FastAPI TestClient 与 Starlette TestClient cookies 的上游弃用警告。
- 已运行 `npm.cmd run lint`，通过。
- 已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 已运行 `git diff --check`，未发现空白或行尾问题。
- 上传上限调整后已重新运行 `uv run ruff check .`、`npm.cmd run lint` 和 `git diff --check`，均通过。
- 缩略图接口和封面选择器分页优化后已重新运行 `uv run ruff check .`、`uv run pytest tests\test_admin_files_api.py tests\test_public_content_api.py`、`npm.cmd run lint` 和 `npm.cmd run build`，均通过；`npm.cmd run build` 仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 公开页封面缩略图接入后已重新运行 `uv run ruff check .`、`uv run pytest tests\test_admin_files_api.py tests\test_public_content_api.py`、`npm.cmd run lint` 和 `npm.cmd run build`，均通过；`npm.cmd run build` 仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 已使用本地真实运行后端解密请求 `GET /api/public/posts?limit=5&offset=0`，确认公开文章列表返回的 `cover_image_url` 为 `/api/public/posts/{slug}/files/{file_id}/thumbnail?...`；随后直接请求该公开缩略图地址返回 `200 image/jpeg`，示例响应大小约 25KB。
- 已运行 `uv run ruff check .`，通过。
- 已运行 `uv run pytest tests\test_admin_content_api.py tests\test_content_service.py tests\test_markdown_provider.py`，15 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 已运行 `npm.cmd run lint`，通过。
- 已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 已运行 `git diff --check`，未发现空白或行尾问题。
- 已重启后端并确认 `http://127.0.0.1:18080/healthz` 返回 200。
- 已检查本项目开发端口，确认 `18080`、`15173`、`14173` 均无监听。
- 列表分页、后台设置分区和移动端布局修正后已重新运行 `npm.cmd run lint`，通过。
- 列表分页、后台设置分区和移动端布局修正后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 移动端文章列表封面和返回按钮遮挡修复后已重新运行 `npm.cmd run lint` 与 `npm.cmd run build`，均通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 移动端公开页边距和后台登录页返回入口修复后已重新运行 `npm.cmd run lint` 与 `npm.cmd run build`，均通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 后台移动端总览溢出修复后已重新运行 `npm.cmd run lint` 与 `npm.cmd run build`，均通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 后台“最近素材”内部溢出修复后已重新运行 `npm.cmd run lint` 与 `npm.cmd run build`，均通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 后台维护任务入口和加密会话清理 CLI 接入后已运行 `uv run ruff check .`，通过。
- 后台维护任务入口和加密会话清理 CLI 接入后已运行 `uv run pytest tests\test_admin_encryption_api.py tests\test_encryption.py`，8 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 已运行 `uv run python -m app.cli --help`，确认 `cleanup-encryption-sessions` 子命令已注册。
- 后台私有文件鉴权下载接入后已运行 `uv run ruff check .`，通过。
- 后台私有文件鉴权下载接入后已运行 `uv run pytest tests\test_admin_files_api.py`，14 个测试通过；仍存在 FastAPI TestClient 与 per-request cookies 的上游弃用警告。
- 后台文件详情下载按钮接入后已运行 `npm.cmd run lint`，通过。
- 后台文件详情下载按钮接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 软删除文件物理清理任务接入后已运行 `uv run ruff check .`，通过。
- 软删除文件物理清理任务接入后已运行 `uv run pytest tests\test_file_cleanup.py`，3 个测试通过。
- 已重新运行 `uv run pytest tests\test_admin_files_api.py tests\test_file_cleanup.py`，17 个测试通过；仍存在 FastAPI TestClient 与 per-request cookies 的上游弃用警告。
- 已运行 `uv run python -m app.cli --help`，确认 `cleanup-deleted-files` 子命令已注册。
- 孤儿文件清理任务接入后已运行 `uv run ruff check .`，通过。
- 孤儿文件清理任务接入后已运行 `uv run pytest tests\test_file_cleanup.py`，6 个测试通过。
- 已重新运行 `uv run pytest tests\test_admin_files_api.py tests\test_file_cleanup.py`，20 个测试通过；仍存在 FastAPI TestClient 与 per-request cookies 的上游弃用警告。
- 已重新运行 `uv run python -m app.cli --help`，确认 `cleanup-orphan-files` 子命令已注册。
- 已重新运行 `git diff --check`，未发现空白或行尾问题。
- 已重新运行后端全量 `uv run pytest`，85 个测试通过；仍存在 FastAPI TestClient 与 per-request cookies 的上游弃用警告。

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
- 将后台 `/admin/files` 从总览占位替换为文件管理页，包含文件搜索、文件列表、对象 key、可见性、引用信息和上传策略区。
- 将后台 `/admin/links` 从总览占位替换为友链与导航管理页，包含友链审核详情和小网站导航条目列表。
- 将后台 `/admin/settings` 从总览占位替换为站点设置页，包含公开站点信息表单、设置预览、社交入口和生产边界摘要。
- 新增前端文件管理临时数据模块，复用到总览文件队列和文件管理页。
- 后台总览“最近文章”和文章统计已从 `samplePosts` 切换为真实后台文章接口，避免继续显示演示文章。
- 清理前端公开友链、导航和站点设置中的 `example.com` / `example.org` 占位 URL，改为当前项目或账号相关入口。
- 新增后台设置 Repository、Service、Schema 和 Admin API，提供 `GET /api/admin/settings` 与 `PATCH /api/admin/settings/{key_name}`，设置列表和保存响应使用 `sensitive-v1` 加密信封，写入接口继续要求 CSRF 与 `setting:write` 权限。
- 前端 `/admin/settings` 已接入真实后台设置接口，读取并保存 `site_profile` 站点基础资料；保存成功后刷新查询缓存并提示“设置已保存”。
- 新增后台友链与导航 Repository、Service、Schema 和 Admin API，提供 `GET /api/admin/friend-links`、`PATCH /api/admin/friend-links/{link_id}/review` 与 `GET /api/admin/site-items`。
- 友链和导航后台接口统一使用 `content-v1` 加密信封；友链审核写操作继续要求 CSRF 与 `friend_link:review` 权限，导航读取入口要求 `site_nav:write` 权限。
- 前端 `/admin/links` 已从 `sampleLinks` / `sampleSites` 切换到真实后台接口，支持读取友链列表、审核通过/拒绝和读取导航条目。
- 后台友链接口补齐 `POST /api/admin/friend-links` 与 `PATCH /api/admin/friend-links/{link_id}`，创建和更新请求均使用 `content-v1` 加密请求体、CSRF 与 `friend_link:review` 权限。
- 前端 `/admin/links` 启用友链新建和编辑表单，保存后刷新真实友链列表并保留审核通过/拒绝操作。
- 修复加密篡改测试的构造方式，改为篡改 base64url 解码后的真实密文字节，避免只修改编码尾位时未改变密文内容。
- 后台导航条目接口补齐 `POST /api/admin/site-items` 与 `PATCH /api/admin/site-items/{item_id}`，创建和更新请求均使用 `content-v1` 加密请求体、CSRF 与 `site_nav:write` 权限。
- 前端 `/admin/links` 新增导航条目管理面板组件，支持导航新建、编辑和列表刷新；同时将 `AdminLinksPage` 从 576 行拆分到 335 行，避免页面文件继续堆积复杂业务逻辑。
- 新增后台文件 Repository、Service、Schema、本地存储 Provider 和 Admin API，提供 `GET /api/admin/files`、`POST /api/admin/files` 与 `DELETE /api/admin/files/{file_id}`。
- 文件列表、上传和删除响应统一使用 `content-v1` 加密信封；上传接口使用 multipart、CSRF 与 `file:upload` 权限，删除接口使用 CSRF 与 `file:delete` 权限。
- 文件上传支持 JPEG、PNG、GIF、WebP 和 PDF 白名单，校验扩展名、MIME 与文件头；新上传文件不再生成 `/uploads/...` 公开 URL，公开文件改为按需生成短时签名访问链接。
- 新增 `BLOG_UPLOAD_MAX_SIZE_BYTES` 配置并同步本地与部署环境变量示例；当前默认限制为 10MB。
- 前端 `/admin/files` 已从临时 `sampleFiles` 切换到真实后台接口，支持文件搜索、上传、软删除，并对公开文件按需生成、复制和打开短时访问链接；私有文件不显示公开链接。
- 补充后台文件 API 测试，覆盖 `content-v1` 加密响应、multipart 上传和删除入口。
- 后台总览页文件统计和“最近素材”已切换到真实后台文件接口，移除不再引用的 `sampleFiles` 临时数据文件，避免继续展示假文件。
- 清理后台和前台显得过于工程说明化的展示文案：删除设置页“登录与发布”说明块，将“安全基线”“生产边界”“上传策略”“后端 sanitize”等界面文案改为更贴近个人博客后台的日常说法。
- 公开文章、友链和站点目录读取已接入 `/api/public/encryption/sessions` 颁发的 public scope 会话，统一返回 `content-v1` 加密响应；加密信封不再携带 `encrypted` 与 `algorithm` 冗余字段。
- 新增公开文件下载入口 `/api/public/files/{file_id}/download?token=...`，后台通过加密接口生成带过期时间的访问链接，不再挂载上传目录为静态目录。
- 前端公开友链、站点目录和首页常用入口已移除 `sampleLinks` / `sampleSites` 假数据，改为读取真实 Public API。
- 新增文章正文图片渲染专用接口 `/api/public/posts/{slug}/files/{file_id}/render`，校验公开文章、公开 active 图片文件和文章内容引用关系后返回图片，避免 Markdown 正文图片依赖临时下载链接。
- 新增 `access_logs` 表、Repository/Service 和后台 `GET /api/admin/access-logs` 查询接口；公开内容读取、公开文件下载、文章图片渲染和后台短时链接生成都会写入访问日志。
- 后台日志接口已改为 `sensitive-v1` 加密响应，前端新增 `/admin/logs`，使用“访问 / 登录 / 事件”标签切换和固定高度列表，避免日志变多后撑长整页。
- 新增后台文章实时预览接口 `POST /api/admin/posts/preview`，使用 `content-v1` 加密请求、CSRF 与 `post:write` 权限，前端编辑正文或 slug 后会防抖请求真实后端 Markdown 渲染结果，不再必须点击保存才更新预览。
- 新增后台文件图片预览接口 `GET /api/admin/files/{id}/preview`，通过短时签名参数访问，后台文章预览中的 `/api/public/posts/{slug}/files/{file_id}/render` 图片引用会被转换为后台签名预览 URL。
- 公开文章详情返回时会把正文图片渲染地址补上 `expires` 与 `token`，裸访问文章图片渲染接口会返回 403，避免访客直接复制无签名接口长期打开或下载。
- 后台文件详情新增“复制文章引用”，复制格式为 `![文件名](/api/public/posts/{slug}/files/{file_id}/render)`，用于文章 Markdown 中保存稳定引用，再由公开详情或后台预览按场景签名。
- 新增公开站点资料接口 `/api/public/settings/site-profile`，首页、公开布局品牌、后台布局品牌和页面标题已读取真实站点设置；后台设置保存后会刷新公开站点资料缓存。
- 修复后台 Markdown 工具栏点击空白也插入图片语法的问题，将原先包裹按钮的标签结构改为普通字段组，只有点击链接或图片按钮才插入对应语法。
- 修复开发环境前端渲染 `/api/...` 图片时错误请求前端端口的问题，`MathHtml` 会把相对 API 资源地址转换到配置中的后端 API 地址。
- 使用本机真实 MySQL 运行库核对文件记录，确认文章引用的文件 `id=6` 指向 `public/2026/06/3d09695ad2e289b5a041f4c8.jpg`；因物理文件缺失导致后台预览 404，已从 `E:\文件\收藏图片\美图\140240924_p0_master1200.jpg` 恢复到上传目录。
- 后台文章创建、更新和发布流程新增文件使用记录同步：`cover_file_id` 记录为 `cover`，Markdown 正文中的 `/api/public/posts/{slug}/files/{file_id}/render` 引用记录为 `post_body`。
- 后台文章加密 API schema、前端类型和文章编辑表单已接入 `cover_file_id`，当前先以文件 ID 输入方式衔接现有文件管理页，后续再升级为文件选择器。
- 后台文章页抽离表单默认值、slug 校验和表单转换工具到 `features/content/postForm.ts`，将页面文件从 407 行降到 391 行。
- 修复实时预览 KaTeX 渲染后又被覆盖的问题：`MathHtml` 改为在 `useLayoutEffect` 中写入 HTML 并渲染公式，避免 React 后续状态重渲染再次覆盖已处理 DOM。
- 后端 Markdown 渲染启用表格语法，并放行 sanitize 后的 `table`、`thead`、`tbody`、`tr`、`th`、`td` 标签；前台正文和后台预览补充分隔线、斜体和表格样式。
- 修复新建文章默认 slug 为空导致保存体验差的问题：新建表单会按当前文章数生成 `post-N`，并跳过已有 slug。
- 后台文件列表和详情显示文件 ID，详情支持复制 ID，封面文件 ID 输入现在有明确来源。
- 前端 API client 会读取后端错误 `detail`，文章保存时将 slug 冲突、文件不存在和表单不完整映射为中文提示。
- 将后台文件详情拆分到 `features/files/FileDetail.tsx`，`AdminFilesPage` 回落到 291 行；`AdminPostsPage` 保持 398 行。
- 同步根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，标记公开文件栏已完成，并更新文件引用追踪与后续计划。

### 进行中

- M1 认证与后台框架继续推进；后台登录、Cookie 会话、CSRF、权限菜单、`sensitive-v1` 加密响应、后台日志查询、入口限流、后台文章与页面管理接口已形成第一版后端闭环。文章、页面、文件、友链/导航、设置页和日志页已具备真实接口入口，后台文章编辑已接入不落库的真实预览渲染，公开前台文章、友链、站点目录、站点资料和文件访问已接入 public scope 的真实加密 Public API 与签名文件访问链路。

### 阻塞与风险

- 待确认真实域名、服务器环境、证书申请方式和对象存储选择。
- 当前限流器为单进程内存实现，适合 M1 单进程验证；生产多进程、多实例或横向扩展前，需要替换为 Redis 等共享存储适配器。
- 应用层加密协商已改为数据库保存短期会话密钥；仍需补充过期会话定时清理和更多审计记录。
- 公开文章、友链和站点目录已接入真实 Public API，但仍需补充更多端到端数据联调和公开空态视觉核验。
- 文件管理已形成列表、上传、软删除、公开文件栏、公开短时链接、文章正文图片渲染、后台签名预览、文章封面和正文图片使用记录最小闭环；私有文件鉴权下载、更多使用场景引用追踪、封面选择器、前台封面展示和物理清理任务仍需继续补齐。
- 本次已启动前后端和本机 MySQL 临时库完成真实登录、加密协商、文章创建、文章发布和页面创建联调；联调后按要求关闭前后端开发服务。
- 本次按用户最新要求，完成可验证小步后自动 commit 并 push。

### 下一步

- 继续将文件管理接入私有文件鉴权下载、更多使用场景引用追踪和物理清理任务。
- 将文章封面从手填文件 ID 升级为后台文件选择器，并在前台列表与详情中展示封面。
- 补充加密会话过期清理任务，并评估 Redis 限流适配器。
- 使用真实 MySQL 运行库继续做“后台上传图片 -> 复制文章引用 -> 设置封面 -> 文章实时预览 -> 发布文章 -> 前台首页、列表、详情图片可见 -> 公开文件栏下载 -> 后台日志可查”的端到端联调。

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
- 后台非文章管理页补齐后已重新运行 `npm.cmd run lint`，通过。
- 后台非文章管理页补齐后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 后台非文章管理页补齐后已重新运行 `git diff --check`，通过。
- 已扫描 `frontend/src`，确认不再残留 `example.com`、`example.org`、`hello@example` 等前端展示占位域名。
- 已临时启动后端 `18080` 与前端 `15173`，通过 Playwright CLI + Microsoft Edge 验证 `/admin/files`、`/admin/links`、`/admin/settings` 均渲染为独立管理页；回到 `/admin` 后确认“最近文章”显示真实后台文章数据，不再显示 `samplePosts` 演示文章。
- 后台设置接口接入后已重新运行 `uv run ruff check .`，通过。
- 后台设置接口接入后已重新运行 `uv run pytest`，45 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 后台设置前端接入后已重新运行 `npm.cmd run lint`，通过。
- 后台设置前端接入后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 后台设置接口接入后已重新运行 `git diff --check`，通过。
- 已临时启动后端 `18080` 与前端 `15173`，通过浏览器登录后台并在 `/admin/settings` 点击“保存设置”，确认真实设置接口可保存并返回“设置已保存”提示。
- 后台友链与导航接口接入后已重新运行 `uv run ruff check .`，通过。
- 后台友链与导航接口接入后已重新运行 `uv run pytest tests/test_admin_links_api.py`，5 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 后台友链创建编辑接入后已重新运行 `uv run pytest`，50 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 后台导航写入接入后已重新运行 `uv run pytest tests/test_admin_links_api.py`，7 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 后台导航写入接入后已重新运行 `uv run pytest`，52 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 后台友链与导航前端接入后已重新运行 `npm.cmd run lint`，通过。
- 后台友链与导航前端接入后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 后台友链创建编辑前端接入后已重新运行 `npm.cmd run lint`，通过。
- 后台友链创建编辑前端接入后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 后台导航写入前端接入和面板拆分后已重新运行 `npm.cmd run lint`，通过。
- 后台导航写入前端接入和面板拆分后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 后台文件 API 接入后已重新运行 `uv run ruff check .`，通过。
- 后台文件 API 接入后已运行 `uv run pytest tests/test_admin_files_api.py`，3 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 后台文件前端接入后已重新运行 `npm.cmd run lint`，通过。
- 后台文件前端接入后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 已使用真实 MySQL 临时库 `blog_codex_files_verify` 运行 Alembic 迁移并创建临时管理员，通过真实后端 API 验证加密协商、后台登录、`POST /api/admin/files` multipart 上传、`GET /api/admin/files` 列表读取和 `DELETE /api/admin/files/{file_id}` 软删除；上传对象 key 为 `public/2026/06/c47dd9465c00e9a0c8b85e9e.png`，物理文件曾写入 `backend/var/uploads-files-verify`。
- 已按用户提醒改用当前 `.env` 的真实本地库 `blog_codex_runtime` 做浏览器可见联调，通过真实 API 上传并保留 1 条文件记录；已确认额外临时库 `blog_codex_files_verify` 不存在，当前 MySQL 仅剩 `blog_codex_runtime` 这个博客本地库。
- 设置页说明块删除和前端文案清理后已重新运行 `npm.cmd run lint`，通过。
- 设置页说明块删除和前端文案清理后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 已临时启动后端 `18080` 与前端 `15173`，通过 Playwright CLI + Microsoft Edge 登录后台并打开 `/admin/links`，确认友链列表和导航条目接口均返回 200，页面显示真实接口空态；登录前 `/api/admin/auth/me` 的 401 属于会话探测预期现象。
- 后台友链与导航接入后已重新运行 `git diff --check`，通过；验证后已关闭临时前后端服务，确认 `18080` 与 `15173` 无监听。
- 已临时启动后端 `18080` 与前端 `15173`，通过 Playwright CLI + Microsoft Edge 登录后台，在 `/admin/links` 新建“Codex验证友链”并编辑为“Codex验证友链已编辑”，确认 `POST /api/admin/friend-links` 与 `PATCH /api/admin/friend-links/1` 均返回 200；验证后已关闭临时前后端服务。
- 后台友链创建编辑接入后已重新运行 `git diff --check`，通过；验证后确认 `18080` 与 `15173` 无监听。
- 已临时启动后端 `18080` 与前端 `15173`，通过 Playwright CLI + Microsoft Edge 登录后台，在 `/admin/links` 新建“Codex验证导航”并编辑为“Codex验证导航已编辑”，确认 `POST /api/admin/site-items` 与 `PATCH /api/admin/site-items/1` 均返回 200；验证后已关闭临时前后端服务。
- 后台导航写入接入后已重新运行 `git diff --check`，通过；验证后确认 `18080` 与 `15173` 无监听。
- 公开加密、文件访问与日志接入后已重新运行 `uv run ruff check .`，通过。
- 公开加密、文件访问与日志接入后已重新运行 `uv run pytest`，69 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 公开加密、文件访问与日志接入后已重新运行 `npm.cmd run lint`，通过。
- 公开加密、文件访问与日志接入后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 本次文章文件使用记录小步已运行 `uv run pytest tests\test_content_service.py tests\test_admin_content_api.py tests\test_admin_files_api.py`，20 个测试通过；仍存在 FastAPI TestClient 与 Starlette cookies 弃用警告。
- 本次文章文件使用记录小步已运行 `npm.cmd run lint`，通过。
- 本次实时预览覆盖修复后已运行 `npm.cmd run lint`，通过。
- 本次实时预览覆盖修复后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 本次 Markdown 表格、默认 slug、文件 ID 来源和保存错误提示修复后已运行 `uv run pytest tests\test_markdown_provider.py tests\test_content_service.py tests\test_admin_content_api.py tests\test_admin_files_api.py`，25 个测试通过；仍存在 FastAPI TestClient 与 Starlette cookies 弃用警告。
- 本次 Markdown 表格、默认 slug、文件 ID 来源和保存错误提示修复后已运行 `npm.cmd run lint`，通过。
- 本次 Markdown 表格、默认 slug、文件 ID 来源和保存错误提示修复后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 文章实时预览、签名图片预览和站点资料接入后已重新运行 `uv run ruff check .`，通过。
- 文章实时预览、签名图片预览和站点资料接入后已重新运行 `uv run pytest`，69 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 文章实时预览、签名图片预览和站点资料接入后已重新运行 `npm.cmd run lint`，通过。
- 文章实时预览、签名图片预览和站点资料接入后已重新运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 已重启后端 `18080` 与前端 `15173`，确认 `/healthz` 和前端首页返回 200。
- 已通过真实后端日志确认 `/api/admin/posts/preview` 返回 200，恢复缺失物理文件后，文章预览图片对应的 `/api/admin/files/6/preview?...` 不再因文件缺失而 404。

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
