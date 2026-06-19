# 项目进度

## 2026-06-19

### 已完成

- 基于最新安全审计结论确认本轮修复边界：生产流量默认经 Nginx，后端不直接暴露公网；文件上传、图片上传、友链和站点 URL 通过管理员操作或审核后才进入公开链路。
- 梳理待修复安全项优先级：优先处理公开加密会话应用层限流、公开 RSS/sitemap 高成本 GET 缓存与日志压力、加密信封和 Markdown 正文字段长度上限；随后处理管理员配置 URL 统一校验、友链健康检查 SSRF 防御纵深、上传大小配置一致性和图片像素限制。
- 明确数据库迁移检查要求：本轮修复若新增或修改数据库字段、索引、约束或默认值，必须同步评估并补充 Alembic 迁移脚本；仅调整 Pydantic schema、Service 逻辑、配置示例或 Nginx 模板时不新增迁移。
- 公开加密会话已接入应用层限流和单 IP 活跃会话上限：`backend/app/api/public/encryption.py` 现在会复用后台限流服务，并在 `encryption_sessions` 中记录 `client_ip`，以限制同 IP 的 public scope 活跃 session 数量。
- 新增 Alembic 迁移 `20260619_0007_encryption_session_client_ip.py`，为 `encryption_sessions` 增加 `client_ip` 字段和组合索引 `scope/client_ip/expires_at`，用于公开加密会话活跃上限统计。
- RSS、sitemap 和 robots.txt 已补充 `Cache-Control` / `ETag`；当客户端命中 `If-None-Match` 时返回 `304`，并跳过应用层访问日志写入，减少公开高成本 GET 的重复开销。
- 加密信封和 Markdown 正文已补充业务长度上限：`session_id`、`nonce`、`ciphertext`、`content_md` 都加了最大长度校验，避免解密、JSON、Markdown 渲染和 sanitize 的无界输入。
- 友链与站点相关 URL 已统一校验：友链 URL 只允许 `http/https`，站点导航和站点资料社交入口允许 `http/https/mailto/站内路径`，并在保存与回读时过滤危险协议。
- 友链健康检查已补充 SSRF 防御纵深：会拒绝解析到 localhost、内网、链路本地、multicast、reserved 和 unspecified 地址的目标，并在重定向链路上重复校验。
- 文件上传已统一到 Nginx 的 20m 限制：后端默认/示例上传上限改为 `20971520`，前端上传提示同步改为 20MB，并补充图片像素与 Pillow 解压炸弹防护。
- 补充后端与前端测试：新增公开加密会话限流、公开加密会话活跃上限、feed 304、站点资料 URL 过滤、友链/站点 URL 校验、SSRF 私网拒绝、Markdown/密文长度和图片像素限制回归测试。
- 修复 `asyncmy 0.2.11` 依赖级风险：后端运行依赖切换为 `aiomysql`，`uv.lock`、本地/部署环境示例、Alembic 示例连接串和 README 均改为 `mysql+aiomysql://`；配置层会临时把旧 `mysql+asyncmy://` 前缀归一化到 `aiomysql`，避免本地遗留 `.env` 直接导致启动失败。
- 公开 `content-v1` 加密 GET 已增加业务查询前置会话校验：公开分类、标签、文章、页面、站点资料、友链、站点目录和公开文件列表/短链接口会先验证 public scope 加密会话，缺少或无效 `X-Encryption-Session` 时不再先触发数据库列表、详情或总数查询。
- `client_ip()` 已改为仅信任配置内反向代理：新增 `BLOG_TRUSTED_PROXY_HOSTS`，支持 IP 和 CIDR，只有直接连接来源属于可信代理时才读取 `X-Forwarded-For` / `X-Real-IP`；后端直连会使用连接 IP，降低伪造代理头绕过限流或污染日志的风险。
- 公开访问日志压力已收敛：原先按类型跳过高频成功访问的策略已调整为 `BLOG_ACCESS_LOG_DEDUPE_SECONDS` 短时去重；同一 IP 在窗口内重复 `GET/HEAD` 同一 path 只写入第一条 `access_logs`，不把 query、临时 token 或签名参数纳入去重 key，生产 Redis 可用时使用 Redis `SET NX EX`，否则回落进程内缓存；错误访问、公开友链申请、公开站点跳转、后台短时链接和后台下载仍记录。
- 公开和后台列表分页已增加统一 `offset` 业务上限：新增 `PAGE_OFFSET_MAX = 10000` 并接入公开内容、公开文件、后台内容、后台文件、后台友链/导航和后台日志列表接口，避免超大 offset 造成深分页压力。
- 按最新部署决策删除仓库内 `deploy/docker-compose.host-nginx.yml`；宿主机 Nginx 场景改为使用服务器本地 `deploy/docker-compose.local.yml` 覆盖文件绑定后端回环端口，避免把机器特定端口策略提交进仓库。
- 继续全量审计后补充管理员刷新令牌边界：`POST /api/admin/auth/refresh` 不再接受 JSON body 中的 `refresh_token`，只读取 HttpOnly Cookie，减少刷新令牌进入前端 JS/请求体日志的兼容面。
- 继续全量审计后补充后台设置和公开站点资料边界：后台设置 `key_name` 增加路径参数格式限制，`value_json` 增加 32KiB 业务体积上限，`site_profile` 保存和公开读取时会截断长字符串、限制碎念/社交链接数量，并过滤不适合图片源的头像协议。
- 继续全量审计后补充上传读取内存边界：后台 multipart 上传现在只读取 `BLOG_UPLOAD_MAX_SIZE_BYTES + 1` 字节并提前返回 413，避免后端被绕过 Nginx 时先把超大文件完整读入内存。
- 修正同 SHA256 上传复用语义：仅当旧文件 active 且可见性、公开列表状态、原始文件名、MIME、扩展名和 alt 文案都与本次上传一致时才复用，避免私有/公开元数据被旧记录“串用”。
- 生产配置新增启动期校验：生产环境 `BLOG_PUBLIC_BASE_URL` 必须是带 host 的 `https://` 绝对地址，防止 RSS、sitemap、robots.txt 和 canonical/签名链接因误配置输出危险或畸形 URL。
- 宿主机 Nginx 维护脚本补齐：`backup_mysql.sh`、`restore_mysql.sh` 和 `upgrade_backend_db.sh` 支持通过 `COMPOSE_EXTRA_FILES` 追加服务器本地覆盖文件，文档已同步 `deploy/docker-compose.local.yml` 示例。
- 前端后台友链和站点导航编辑页的“打开链接”预览按钮新增协议白名单，只允许 `http/https/mailto/站内路径`，未保存的危险协议会降级为 `#`。
- 修复公开 API 反向依赖后台模块的架构问题：新增 `backend/app/api/dependencies.py`、`backend/app/api/encrypted_response.py` 和 `backend/app/api/limits.py` 作为 admin/public 共享 API 层，公开路由不再从 `app.api.admin.*` 引入服务依赖、加密响应或限流工具；后台路由也改为直接引用共享层，`app.api.admin.dependencies` 仅保留后台认证、CSRF、权限和后台专属依赖。
- 拆分公开路由职责：`backend/app/api/public/router.py` 缩减为子路由聚合器，新增 `common.py`、`taxonomy.py`、`posts.py`、`settings.py` 和 `links.py`，分别承载公开共享校验/日志、分类标签、文章页面、站点资料、友链与站点导航逻辑；公开 URL、响应模型和错误码保持不变。
- 拆分 `FileService` 的横向职责：新增 `backend/app/services/file_errors.py`、`file_tokens.py`、`file_uploads.py` 和 `file_storage.py`，分别承载文件异常、临时 token/文章图片 URL 签名、上传校验/文件头/图片尺寸、存储路径/缩略图/引用校验；`backend/app/services/files.py` 缩减为文件用例编排，并保留原公开导入出口兼容现有 API 和测试。
- 公开读取接口已引入 Service read model 边界：新增 `backend/app/services/content_read_models.py` 和 `file_read_models.py`，公开文章列表/详情、公开页面、公开分类标签和公开文件列表由 Service 返回只读 DTO，API 层不再直接依赖这些公开链路的 ORM 模型字段；文章图片渲染仍通过公开文章 detail read model 提供引用校验所需正文摘要字段。
- Service 更新入口已改为显式命令对象：新增 `backend/app/services/update_commands.py`，`ContentService`、`LinkService` 和 `LinkGroupService` 的更新方法改为接收 `UpdatePostCommand`、`UpdatePageCommand`、`UpdateFriendLinkCommand`、`UpdateSiteNavItemCommand`、`UpdateFriendLinkGroupCommand` 和 `UpdateSiteNavGroupCommand`，保留 PATCH 未传字段不更新、显式 `null` 清空字段的语义，并移除业务更新中的 `dict + setattr` 模式。
- 后台链接路由已按资源职责拆分：`backend/app/api/admin/links.py` 缩减为聚合器，新增 `links_common.py`、`link_groups.py`、`friend_links.py` 和 `site_nav.py`，分别承载共享加密/校验/异常/audit helper、分组 CRUD、友链 CRUD/审核和站点导航 CRUD；原 `/api/admin/friend-link-groups`、`/site-groups`、`/friend-links`、`/site-items` URL 和响应保持不变。
- 后台文章和页面编辑状态已从路由组件抽出：新增 `useAdminPostEditor` 和 `useAdminPageEditor`，将列表查询、分页、选中态、表单态、保存/发布 mutation、预览状态和缓存失效收敛到 feature hook，`AdminPostsPage` 与 `AdminPagesPage` 只保留页面编排和 JSX。
- API 共享依赖缓存已从模块全局状态迁移到 `FastAPI app.state`：新增 `backend/app/api/state.py`，在 `create_app()` 初始化访问日志去重 backend 和限流服务，dependency 按配置签名从当前 app state 懒加载，避免多 app 实例、测试覆盖或热切换配置时复用错误全局实例。
- 前端重复分页、查询页码和空字符串归一化已抽为共享工具：新增 `usePagedItems`、`useQueryPage` 和 `utils/formText.ts`，后台文件/日志/文章/页面/友链/站点导航与公开文件/友链/站点/文章归档复用统一分页和 page query 逻辑，移除多处局部 `parsePage`、`emptyToNull/nullableText` 和手写 `safeListPage + slice`。
- 后台设置页状态和表单转换已从路由组件抽出：新增 `siteProfileForm.ts` 和 `useAdminSiteProfileEditor`，将站点资料加载、表单归一化、分区状态、保存 mutation 和缓存失效移入 settings feature；`AdminSettingsPage` 缩减为页面布局、表单 JSX 和预览渲染。
- 后台友链和站点导航面板状态职责已抽出：新增 `useAdminFriendLinksEditor`、`useAdminSiteNavEditor` 和 `siteNavForm.ts`，将列表查询、分页、选中态、表单态、保存/审核 mutation、缓存失效和表单转换移入 links feature hook；面板文件保留 JSX 编排和展示逻辑。
- 后端管理端读取边界已收敛到 Service read model：内容与文件服务新增管理端 DTO/read 方法，日志服务返回只读日志 DTO，设置服务新增后台设置 DTO 和公开站点资料 DTO；后台内容、文件、日志、设置 API 不再直接从 ORM/record 自行扫字段，公开站点资料清洗也从路由搬入 `SettingService`。
- 前后端类型手写镜像已补充契约测试：新增 `backend/tests/test_frontend_contract.py`，按字段名、可空性、数组和对象形状校验后端 Pydantic 响应 schema 与前端 `features/*/types.ts` 的主要响应类型，降低后续手写类型漂移风险。
- 全局 CSS 已按职责拆分：`frontend/src/index.css` 改为聚合导入，新增 `frontend/src/styles/base.css`、`public.css`、`prose.css`、`components.css`、`admin.css`、`forms.css` 和 `responsive.css`，保持原有规则顺序和视觉行为不变。
- 修复宿主机 Nginx + Docker 后端场景下访问日志 IP 易显示为 Docker 网关的问题：`client_ip()` 在可信代理连接下会从 `X-Forwarded-For` 右侧开始跳过可信代理，取第一个非可信客户端 IP，避免简单取最左值被伪造头污染；部署示例将 `BLOG_TRUSTED_PROXY_HOSTS` 调整为 Docker bridge CIDR 示例，并补充 `172.23.0.1` 类网关地址的配置说明。
- P1 上传静态暴露已修复：删除 Compose 内置 Nginx 的 `/uploads/` 静态 location、删除 nginx 服务对 `/data/blog/uploads/public` 的只读挂载，并移除 nginx 镜像内上传目录创建；README、部署 README 和计划书同步明确上传目录不能挂到 Nginx 静态目录，公开文件、文章图片和后台预览必须继续走后端签名接口。该修复不涉及数据库迁移。
- 高优先级文章资源加载浪费已修复：公开文章、页面、归档和分类/标签查询会透传 React Query 的 `AbortSignal`，切换页面时会取消仍在等待的数据请求；`MathHtml` 会先在离线 `template` 中改写 `/api/...` 资源地址再插入 DOM，并在卸载或内容切换时移除 `img/iframe/video/audio` 的加载源，减少无效带宽消耗。
- 文章资源临时 token 已支持浏览器缓存复用：文章正文图片、封面缩略图和后台预览图片的签名 URL 会在半个有效期时间窗内保持稳定，响应增加 `Cache-Control: private, max-age=..., immutable`、`ETag` 和 `X-Content-Type-Options: nosniff`；同一文件在时间窗内重复访问可命中浏览器缓存，过期后仍会自动换签名。
- P2 RSS/sitemap 高成本 GET 已收敛：最近渲染的 RSS 和 sitemap 会短时缓存在应用进程内，缓存未过期时可在业务查询和 XML 渲染前处理 `If-None-Match` 并直接返回 `304`；缓存命中 `200` 仍保留访问日志，缓存命中 `304` 继续跳过访问日志。
- P2 公开站点跳转写放大已收敛：`/api/public/site-items/{item_id}/visit` 会先只读确认公开站点项，再用现有 Redis/内存去重后端按 `IP + item_id` 和 `BLOG_ACCESS_LOG_DEDUPE_SECONDS` 短窗口判断是否递增点击计数、写访问日志；窗口内重复访问仍正常返回 `302`，但不重复写 `click_count` 和 `access_logs`，访问日志不再记录 `click_count/open_target` 明细。
- P2 日志保留清理任务已补齐：新增 `cleanup-logs` CLI、`blog-cleanup-logs.service/timer`、日志保留 Service 和四张日志表按 `created_at` 批量删除能力；默认访问日志保留 30 天，审计/登录/安全事件保留 180 天，每张表单次最多删除 5000 条，天数传 `0` 可跳过对应表。新增 Alembic 迁移 `20260619_0008_log_retention_indexes.py`，为 `audit_logs`、`login_logs` 和 `security_events` 补 `created_at` 索引，`access_logs` 已有索引。
- P2 公开友链申请 URL/域名去重和待审上限已补齐：公开申请入口改用 `create_public_friend_link_application()`，会规范化 URL、拒绝与现有 `pending/healthy` 友链重复的 URL，并限制全站待审数量和同域待审数量；公开申请成功日志不再记录申请 name/url 明细。新增 Alembic 迁移 `20260619_0009_friend_link_status_index.py`，为 `friend_links.status` 补查询索引；未添加 URL 唯一约束，避免历史重复数据阻塞迁移。
- P3 后台 `/api/admin/auth/me` 已前置校验加密会话：新增 `EncryptedCurrentAdminUserDependency`，会先验证 admin scope 的 `sensitive-v1` session，再解析 Access Token 和查询当前用户；缺少或无效 `X-Encryption-Session` 不再触发认证查询。该修复不涉及数据库迁移或服务器环境变量。
- P3 logout 刷新令牌边界已收敛：`POST /api/admin/auth/logout` 不再声明或读取请求体中的 `refresh_token`，只从 HttpOnly `blog_admin_refresh` Cookie 读取并吊销；请求体里携带的 token 会被忽略。该修复不涉及数据库迁移或服务器环境变量。
- P3 公开 href 敏感路径边界已收敛：统一 URL validator 会拒绝公开站内链接指向 `/admin` 和 `/api/admin` 管理入口，前端后台友链/站点导航的未保存链接预览也同步降级危险站内路径为 `#`。该修复不涉及数据库迁移或服务器环境变量。
- P3 访问日志策略漂移已修正：删除后端配置中已不再使用的 `access_log_skip_types` 字段和测试假配置残留，文档统一以 `BLOG_ACCESS_LOG_DEDUPE_SECONDS` 短时去重为准。该修复不涉及数据库迁移；生产不需要新增配置，若曾设置旧 `BLOG_ACCESS_LOG_SKIP_TYPES` 可删除。
- P3 访问日志和审计日志 payload 已最小化：公开访问日志不再写入列表数量、limit/offset、slug、文件名、MIME 或临时链接过期时间；后台审计日志会在写入和读取时按 allowlist 清洗，只保留状态类摘要与 `changed_fields`，过滤标题、slug、URL、文件名、MIME、完整设置值和旧历史 payload 中的敏感字段；登录限流安全事件不再记录具体用户名。该修复不涉及数据库迁移或新增服务器配置。
- P4 后台日志页已改为后端真分页：前端不再固定拉每类前 50 条后本地分页，而是按当前 tab 和页码请求 `limit=pageSize+1`、`offset=page*pageSize`，用额外一条探测是否还有下一页；日志超过 50 条时可继续翻页。该修复不涉及数据库迁移或服务器配置。
- P4 文件服务返回边界已显式化：删除 `FileWithUsage.__getattr__` 动态代理，文件列表、上传和删除用例直接返回 `AdminFileRead`，API 层不再依赖“半 ORM、半 DTO”的隐式属性透传。该修复不涉及数据库迁移或服务器配置。
- P4 前端自动化测试基础已补齐：新增 Vitest、Testing Library 和 jsdom，提供 `npm.cmd test`，并补充 URL 白名单、分页纯函数和后台日志 API `limit/offset` 参数测试，先覆盖本轮安全与分页回归点。该修复不涉及数据库迁移或服务器配置。
- P4 前端 CSS 大文件已继续拆分：`public.css`、`forms.css`、`admin.css` 和 `base.css` 改为职责聚合入口，新增 public、forms、admin、base 分层 CSS 文件；当前 `frontend/src/styles` 下已无 400 行以上 CSS 文件。该修复不涉及数据库迁移或服务器配置。
- P4 `FileService` 大文件已继续拆分：新增 `file_downloads.py` 承载公开/后台下载、文章图片渲染、缩略图和预览访问策略，新增 `file_maintenance.py` 承载软删除文件清理与孤儿文件扫描；`files.py` 降到 379 行，保留文件用例编排和对外兼容导出。该修复不涉及数据库迁移或服务器配置。
- P4 `LogService` 大文件已继续拆分：新增 `access_log_dedupe.py` 承载访问日志短时去重后端和 Redis/内存策略，新增 `log_sanitizers.py` 承载日志 JSON allowlist 清洗；`logs.py` 降到 316 行，并通过 `__all__` 保持旧导入路径兼容。该修复不涉及数据库迁移或服务器配置。
- P4 `ContentService` 大文件已继续拆分：新增 `content_commands.py`、`content_errors.py`、`content_protocols.py` 和 `content_post_helpers.py`，分别承载内容命令对象、异常、Repository 协议和文章文件引用/发布时间/标签归一化 helper；`content.py` 降到 380 行，并通过 `__all__` 保持旧导入路径兼容。该修复不涉及数据库迁移或服务器配置。
- P4 `LinkService` 大文件已继续拆分：新增 `link_commands.py`、`link_constants.py`、`link_errors.py`、`link_protocols.py`、`link_records.py` 和 `link_url.py`，分别承载链接命令、常量、异常、Repository 协议、只读记录和友链 URL 规范化；`links.py` 降到 381 行，旧的 `app.services.links` 具名导入保持兼容。该修复不涉及数据库迁移或服务器配置。
- P4 后台内容路由已按资源职责拆分：`backend/app/api/admin/content.py` 缩减为聚合器，新增 `content_common.py`、`content_posts.py` 和 `content_pages.py`，分别承载内容加密/权限/校验 helper、文章 CRUD/预览/发布、页面 CRUD；原 `/api/admin/posts`、`/api/admin/pages` URL、权限和加密响应契约保持不变。该修复不涉及数据库迁移或服务器配置。
- P4 内容 Repository 已按查询职责拆分：新增 `content_public.py` 承载公开文章、公开页面、feed、分类和标签查询 mixin，新增 `content_helpers.py` 承载标签归一化、slug 生成、公开文章过滤和 taxonomy 映射 helper；`content.py` 降到 247 行，Repository 对外方法签名和返回形状保持不变。该修复不涉及数据库迁移或服务器配置。

### 待修复清单

- P4：仍有多个源码文件超过项目单文件体量建议或接近阈值，后续维护和安全回归成本偏高。当前统计中 `backend/app/api/public/feeds.py` 约 438 行，`backend/app/services/files.py` 约 418 行，`backend/app/api/admin/files.py` 约 398 行，`frontend/src/features/posts/PublicPostArchivePage.tsx` 约 394 行。建议继续按职责拆分 RSS/sitemap 渲染和文件服务剩余编排。

### 进行中

- 正在处理 P4 大文件拆分；下一块聚焦 `backend/app/api/public/feeds.py` 的缓存/路由与 XML 渲染分离。

### 阻塞与风险

- 今日新增的 `encryption_sessions.client_ip`、日志保留索引和友链状态索引需要生产库执行 Alembic 迁移到 head；当前最新迁移为 `20260619_0009_friend_link_status_index.py`。
- 上传上限已从 30MB 收敛到 20MB，服务器上的后端环境变量需要同步为 `BLOG_UPLOAD_MAX_SIZE_BYTES=20971520`，否则会与 Nginx 配置不一致。
- 本次依赖切换需要服务器真实 `deploy/env/backend.env` 同步改为 `BLOG_DATABASE_URL=mysql+aiomysql://...`；代码会临时兼容旧 `mysql+asyncmy://` 前缀，但不建议生产长期保留旧写法。
- 宿主机 Nginx 反代场景需要设置 `BLOG_TRUSTED_PROXY_HOSTS` 为后端看到的宿主机/网关直连 IP 或 CIDR；若日志里显示 `172.23.0.1` 这类 Docker 网关地址，服务器真实 `backend.env` 可填 `BLOG_TRUSTED_PROXY_HOSTS=["172.16.0.0/12"]` 或只填实际网关 IP。
- 生产环境现在会强制校验 `BLOG_PUBLIC_BASE_URL` 为 `https://` 绝对地址；服务器真实 `backend.env` 不能再使用 `http://`、相对路径或占位值。
- 访问日志和公开站点跳转去重窗口可通过 `BLOG_ACCESS_LOG_DEDUPE_SECONDS=60` 显式配置；不配置时默认 60 秒，生产 Redis 已启用时会复用 `BLOG_REDIS_URL`。
- 本机 ignored 的 `deploy/env/backend.env` 仍可能保留旧连接串，`docker compose config` 只能证明配置展开语法有效；生产发布前必须按上面的真实 env 项显式更新。
- P1 修复会影响服务器 Nginx/Compose 部署：如果服务器宿主机 Nginx 手动配置了 `/uploads/` 或等价 alias，需要同步删除；如果使用 Compose 内置 Nginx，需要重建 nginx 镜像并重新展开 Compose 配置。
- 本次文章资源中断加载和签名缓存修复不涉及数据库字段、索引或约束变化，不需要新增 Alembic 迁移；也没有新增、删除或改名服务器环境变量。部署侧只需要发布新的后端代码和前端静态构建产物。

### 下一步

- 继续拆分 `backend/app/api/public/feeds.py`，将 feed 缓存、RSS/sitemap/robots 渲染和访问日志 helper 分离，保持公开 URL、ETag 和 Cache-Control 行为不变。

### 验证

- 本轮按 CTF/红队思路执行只读静态审计，覆盖公开入口、后台认证/会话、文件上传下载、URL/跳转、日志写入、部署暴露面、Markdown/前端危险 sink、配置漂移和工程体量；除写入 `PROJECT_PROGRESS.md` 外未修改业务代码。
- 本轮未运行 `pip-audit` 等依赖扫描命令，避免再次触发本机杀软对审计工具缓存的误报；未启动本地前后端服务。
- P1 上传静态暴露修复后已运行文本检查，确认 `deploy/nginx/templates/blog.conf.template`、`deploy/docker-compose.yml` 和 `deploy/nginx/Dockerfile` 不再包含 `/uploads/` 静态 location、上传目录挂载或 nginx 镜像内上传目录创建。
- 已运行 `uv run ruff check .`，通过。
- 已运行 `uv run pytest tests/test_public_content_api.py tests/test_admin_files_api.py tests/test_request_client_ip.py tests/test_log_service.py tests/test_admin_logs_api.py`，53 个测试通过；仍存在 FastAPI/Starlette TestClient 与 per-request cookies 的上游弃用警告。
- 已运行 `uv run pytest`，141 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 4 个 FastAPI/Starlette 上游弃用警告。
- 已运行 `uv run alembic upgrade head --sql`，可正常生成从空库到当前 head 的 MySQL 迁移 SQL。
- 已运行 `npm.cmd run lint`，通过。
- 已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 已运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config`，配置可展开；本机真实 ignored env 仍需按服务器配置项更新旧数据库连接串。
- 已按当时临时覆盖文件思路验证过 host-nginx 覆盖可展开；随后根据最新要求删除仓库内 `deploy/docker-compose.host-nginx.yml`，后续宿主机 Nginx 部署使用服务器本地 `deploy/docker-compose.local.yml`。
- 尝试运行 Docker 镜像构建时，本机 Docker Desktop 未运行，连接 `dockerDesktopLinuxEngine` 失败；服务器或 Docker 正常运行环境仍需执行构建命令生成最新静态前端镜像。
- 继续全量审计新增修复后已运行 `uv run pytest tests/test_admin_files_api.py tests/test_admin_security.py tests/test_admin_settings_api.py tests/test_public_content_api.py tests/test_url_validation.py`，64 个测试通过；仍存在 FastAPI/Starlette TestClient、per-request cookies 和 HTTP 状态常量的上游弃用警告。
- 继续全量审计新增修复后已运行 `uv run ruff check .`，通过。
- 继续全量审计新增修复后已运行 `npm.cmd run lint`，通过。
- 继续全量审计新增部署脚本后已使用 Git for Windows Bash 运行 `bash -n deploy/scripts/backup_mysql.sh deploy/scripts/restore_mysql.sh deploy/scripts/upgrade_backend_db.sh`，通过；PowerShell 中直接调用 `bash` 会落到当前不可用的 WSL，已改用 `C:\Program Files\Git\bin\bash.exe` 验证。
- 继续全量审计新增修复后已运行 `uv run pytest`，150 个测试通过，2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 7 个 FastAPI/Starlette 上游弃用警告。
- 继续全量审计新增修复后已运行 `uv run alembic upgrade head --sql`，可正常生成从空库到 `20260619_0007` 的 MySQL 迁移 SQL；本轮新增修复未产生新迁移文件。
- 继续全量审计新增修复后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 继续全量审计新增修复后已运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config --quiet`，通过。
- 继续全量审计新增修复后已运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config --quiet`，通过；仓库内 host-nginx 覆盖文件已删除，不再作为提交内容验证。
- 继续尝试运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml build nginx`，本机 Docker Desktop 仍未运行，无法连接 `dockerDesktopLinuxEngine`；服务器或 Docker 正常运行环境仍需执行构建并复制静态文件。
- 访问日志短时去重调整后已运行 `uv run ruff check .`，通过。
- 访问日志短时去重调整后已运行 `uv run pytest tests/test_log_service.py tests/test_public_content_api.py tests/test_admin_files_api.py`，51 个测试通过；仍存在 FastAPI/Starlette TestClient、per-request cookies 和 HTTP 状态常量的上游弃用警告。
- 访问日志短时去重调整后已运行 `uv run pytest`，154 个测试通过，2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 7 个 FastAPI/Starlette 上游弃用警告。
- `ContentService` 拆分后已运行 `uv run ruff check app/services/content.py app/services/content_commands.py app/services/content_errors.py app/services/content_protocols.py app/services/content_post_helpers.py`，通过。
- `ContentService` 拆分后已运行 `uv run pytest tests/test_content_service.py tests/test_admin_content_api.py tests/test_public_content_api.py`，45 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- `LinkService` 拆分后已运行 `uv run ruff check app/services/links.py app/services/link_commands.py app/services/link_constants.py app/services/link_errors.py app/services/link_protocols.py app/services/link_records.py app/services/link_url.py`，通过。
- `LinkService` 拆分后已运行 `uv run pytest tests/test_link_service.py tests/test_admin_links_api.py tests/test_public_content_api.py`，54 个测试通过；仍存在 FastAPI/Starlette TestClient 和 HTTP 状态常量上游弃用警告。
- 后台内容路由拆分后已运行 `uv run ruff check app/api/admin/content.py app/api/admin/content_common.py app/api/admin/content_posts.py app/api/admin/content_pages.py`，通过。
- 后台内容路由拆分后已运行 `uv run pytest tests/test_admin_content_api.py tests/test_content_service.py tests/test_frontend_contract.py`，34 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 内容 Repository 拆分后已运行 `uv run ruff check app/repositories/content.py app/repositories/content_helpers.py app/repositories/content_public.py`，通过。
- 内容 Repository 拆分后已运行 `uv run pytest tests/test_content_service.py tests/test_public_content_api.py tests/test_admin_content_api.py`，45 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- `FileService` 拆分后已运行 `uv run ruff check app/services/file_errors.py app/services/file_tokens.py app/services/file_uploads.py app/services/file_storage.py app/services/files.py tests/test_admin_files_api.py tests/test_file_cleanup.py`，通过。
- `FileService` 拆分后已运行 `uv run pytest tests/test_admin_files_api.py tests/test_file_cleanup.py tests/test_public_content_api.py tests/test_content_service.py`，60 个测试通过；仍存在 FastAPI/Starlette TestClient、per-request cookies 和 HTTP 状态常量的上游弃用警告。
- 公开读取 read model 边界调整后已运行 `uv run ruff check app/schemas/content.py app/services/content_read_models.py app/services/file_read_models.py app/services/content.py app/services/files.py app/api/public tests/test_public_content_api.py tests/test_content_service.py tests/test_admin_files_api.py`，通过。
- 公开读取 read model 边界调整后已运行 `uv run pytest tests/test_public_content_api.py tests/test_content_service.py tests/test_admin_files_api.py`，51 个测试通过；仍存在 FastAPI/Starlette TestClient、per-request cookies 和 HTTP 状态常量的上游弃用警告。
- Service 更新命令改造后已运行 `uv run ruff check app/services/update_commands.py app/services/content.py app/services/links.py app/services/link_groups.py app/api/admin/content.py app/api/admin/links.py tests/test_content_service.py tests/test_admin_links_api.py`，通过。
- Service 更新命令改造后已运行 `uv run pytest tests/test_content_service.py tests/test_admin_content_api.py tests/test_admin_links_api.py tests/test_public_content_api.py`，54 个测试通过；仍存在 FastAPI/Starlette TestClient 和 HTTP 状态常量的上游弃用警告。
- 后台链接路由拆分后已运行 `uv run ruff check app/api/admin/links.py app/api/admin/links_common.py app/api/admin/link_groups.py app/api/admin/friend_links.py app/api/admin/site_nav.py tests/test_admin_links_api.py`，通过。
- 后台链接路由拆分后已运行 `uv run pytest tests/test_admin_links_api.py tests/test_public_content_api.py tests/test_admin_content_api.py`，47 个测试通过；仍存在 FastAPI/Starlette TestClient 和 HTTP 状态常量的上游弃用警告。
- 后台文章/页面编辑状态抽取后已运行 `npm.cmd run lint`，通过。
- 后台文章/页面编辑状态抽取后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- API 共享依赖状态迁移后已运行 `uv run ruff check app/api/state.py app/api/dependencies.py app/main.py tests/test_rate_limit.py tests/test_log_service.py tests/test_public_content_api.py tests/test_admin_encryption_api.py`，通过。
- 文章资源加载修复后已运行 `uv run pytest tests/test_admin_files_api.py`，17 个测试通过；仍存在 FastAPI/Starlette TestClient、per-request cookies 和 HTTP 状态常量的上游弃用警告。
- 文章资源加载修复后已运行 `uv run ruff check app/api/file_cache.py app/api/public/files.py app/api/admin/files.py app/services/file_tokens.py tests/test_admin_files_api.py`，通过。
- 文章资源加载修复后已运行 `uv run pytest`，181 个测试通过，2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 7 个 FastAPI/Starlette 上游弃用警告。
- 文章资源加载修复后已运行 `npm.cmd run lint`，通过。
- 文章资源加载修复后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- RSS/sitemap 缓存短路修复后已运行 `uv run pytest tests/test_public_content_api.py -k "rss or sitemap or robots"`，6 个测试通过，25 个未选中；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- RSS/sitemap 缓存短路修复后已运行 `uv run pytest tests/test_public_content_api.py`，31 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- RSS/sitemap 缓存短路修复后已运行 `uv run ruff check app/api/public/feeds.py tests/test_public_content_api.py`，通过。
- 公开站点跳转短时去重修复后已运行 `uv run pytest tests/test_public_content_api.py -k "site_item_visit"`，3 个测试通过、29 个未选中；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 公开站点跳转短时去重修复后已运行 `uv run pytest tests/test_public_content_api.py`，32 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 公开站点跳转短时去重修复后已运行 `uv run ruff check app/api/public/links.py app/services/links.py app/repositories/links.py tests/test_public_content_api.py`，通过。
- 日志保留清理任务新增后已运行 `uv run pytest tests/test_log_service.py tests/test_admin_logs_api.py`，14 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 日志保留清理任务新增后已运行 `uv run ruff check app/models/log.py app/repositories/logs.py app/services/log_retention.py app/tasks/logs.py app/cli.py tests/test_log_service.py`，通过。
- 日志保留清理任务新增后已运行 `uv run python -m app.cli cleanup-logs --help`，CLI 子命令可正常加载。
- 日志保留清理任务新增后已运行 `uv run alembic upgrade head --sql`，可正常生成从空库到 `20260619_0008` 的 MySQL 迁移 SQL。
- 公开友链申请去重/上限修复后已运行 `uv run pytest tests/test_link_service.py tests/test_public_content_api.py tests/test_url_validation.py`，48 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 公开友链申请去重/上限修复后已运行 `uv run ruff check app/core/url_validation.py app/api/public/links.py app/models/link.py app/repositories/links.py app/services/links.py tests/test_link_service.py tests/test_public_content_api.py tests/test_url_validation.py`，通过。
- 公开友链申请去重/上限修复后已运行 `uv run alembic downgrade 20260619_0009:20260619_0008 --sql`，可正常生成回滚 SQL。
- 公开友链申请去重/上限修复后已运行 `uv run alembic upgrade head --sql`，可正常生成从空库到 `20260619_0009` 的 MySQL 迁移 SQL。
- 后台 `/api/admin/auth/me` 加密会话前置校验修复后已运行 `uv run pytest tests/test_admin_encryption_api.py tests/test_health.py tests/test_admin_security.py`，23 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 后台 `/api/admin/auth/me` 加密会话前置校验修复后已运行 `uv run ruff check app/api/admin/dependencies.py app/api/admin/auth.py tests/test_admin_encryption_api.py tests/test_health.py`，通过。
- logout 刷新令牌边界收敛后已运行 `uv run pytest tests/test_admin_security.py tests/test_admin_encryption_api.py tests/test_frontend_contract.py`，43 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- logout 刷新令牌边界收敛后已运行 `uv run ruff check app/api/admin/auth.py app/schemas/auth.py tests/test_admin_security.py`，通过。
- 公开 href 敏感路径 denylist 修复后已运行 `uv run pytest tests/test_url_validation.py`，18 个测试通过。
- 公开 href 敏感路径 denylist 修复后已运行 `uv run ruff check app/core/url_validation.py tests/test_url_validation.py`，通过。
- 公开 href 敏感路径 denylist 修复后已运行 `npm.cmd run lint`，通过。
- 访问日志策略漂移修正后已运行 `uv run pytest tests/test_log_service.py`，9 个测试通过。
- 访问日志策略漂移修正后已运行 `uv run ruff check app/core/config.py tests/test_log_service.py`，通过。
- 访问日志策略漂移修正后已用 `rg "ACCESS_LOG_SKIP_TYPES|access_log_skip_types|SKIP_TYPES|skip_types" -n` 检查旧配置名，确认仅剩进度文档中的已修正说明。
- 日志 payload 最小化后已运行 `uv run pytest tests/test_log_service.py tests/test_admin_logs_api.py tests/test_admin_content_api.py tests/test_admin_files_api.py tests/test_admin_links_api.py tests/test_admin_settings_api.py tests/test_public_content_api.py tests/test_rate_limit.py`，93 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 日志 payload 最小化后已运行 `uv run pytest tests/test_rate_limit_redis_integration.py`，本地未配置 Redis，2 个集成测试按既有条件跳过。
- 日志 payload 最小化后已运行 `uv run ruff check app/services/logs.py app/api/admin/audit.py app/api/limits.py app/api/admin/auth.py app/api/admin/content.py app/api/admin/files.py app/api/admin/links_common.py app/api/admin/settings.py app/api/public/common.py app/api/public/feeds.py app/api/public/files.py app/api/public/posts.py app/api/public/taxonomy.py app/api/public/links.py app/api/public/settings.py tests/test_log_service.py tests/test_admin_logs_api.py tests/test_admin_content_api.py tests/test_admin_files_api.py tests/test_admin_links_api.py tests/test_admin_settings_api.py tests/test_public_content_api.py tests/test_rate_limit.py`，通过。
- 后台日志真分页修复后已运行 `npm.cmd run lint`，通过。
- 后台日志真分页修复后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 文件服务返回边界显式化后已运行 `uv run pytest tests/test_admin_files_api.py tests/test_file_cleanup.py`，26 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 文件服务返回边界显式化后已运行 `uv run ruff check app/services/files.py app/api/admin/files.py tests/test_admin_files_api.py tests/test_file_cleanup.py`，通过。
- 前端测试基础补齐后已运行 `npm.cmd test`，3 个测试文件、6 个测试通过。
- 前端测试基础补齐后已运行 `npm.cmd run lint`，通过。
- 前端测试基础补齐后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 前端 CSS 大文件拆分后已运行 `npm.cmd run lint`，通过。
- 前端 CSS 大文件拆分后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- `FileService` 下载/维护逻辑拆分后已运行 `uv run pytest tests/test_admin_files_api.py tests/test_file_cleanup.py`，26 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- `FileService` 下载/维护逻辑拆分后已运行 `uv run ruff check app/services/files.py app/services/file_downloads.py app/services/file_maintenance.py tests/test_admin_files_api.py tests/test_file_cleanup.py`，通过。
- `LogService` 去重和清洗逻辑拆分后已运行 `uv run pytest tests/test_log_service.py tests/test_admin_logs_api.py tests/test_rate_limit.py`，20 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- `LogService` 去重和清洗逻辑拆分后已运行 `uv run ruff check app/services/logs.py app/services/access_log_dedupe.py app/services/log_sanitizers.py tests/test_log_service.py tests/test_admin_logs_api.py tests/test_rate_limit.py`，通过。
- API 共享依赖状态迁移后已运行 `uv run pytest tests/test_rate_limit.py tests/test_log_service.py tests/test_public_content_api.py tests/test_admin_encryption_api.py`，49 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 前端分页和表单文本工具抽取后已运行 `npm.cmd run lint`，通过。
- 前端分页和表单文本工具抽取后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 后台设置页状态抽取后已运行 `npm.cmd run lint`，通过。
- 后台设置页状态抽取后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 后台友链和站点导航状态抽取后已运行 `npm.cmd run lint`，通过。
- 后台友链和站点导航状态抽取后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 后端管理端 read model 收敛后已运行 `uv run ruff check app/services/content_read_models.py app/services/content.py app/services/file_read_models.py app/services/files.py app/services/logs.py app/services/settings.py app/api/admin/content.py app/api/admin/files.py app/api/admin/logs.py app/api/admin/settings.py app/api/public/settings.py app/schemas/settings.py tests/test_admin_content_api.py tests/test_admin_files_api.py tests/test_admin_settings_api.py tests/test_public_content_api.py`，通过。
- 后端管理端 read model 收敛后已运行 `uv run pytest tests/test_admin_content_api.py tests/test_admin_files_api.py tests/test_admin_logs_api.py tests/test_admin_settings_api.py tests/test_public_content_api.py tests/test_content_service.py tests/test_log_service.py`，71 个测试通过；仍存在 FastAPI/Starlette TestClient、per-request cookies 和 HTTP 状态常量的上游弃用警告。
- 前后端类型契约测试新增后已运行 `uv run ruff check tests/test_frontend_contract.py`，通过。
- 前后端类型契约测试新增后已运行 `uv run pytest tests/test_frontend_contract.py -q`，23 个测试通过。
- CSS 拆分后已用脚本确认 7 个样式分层按导入顺序拼接后，忽略空白与原 `frontend/src/index.css` 规则内容一致。
- CSS 拆分后已运行 `npm.cmd run lint`，通过。
- CSS 拆分后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 全部待修复项完成后已运行 `uv run ruff check .`，通过。
- 全部待修复项完成后已运行 `uv run pytest`，177 个测试通过，2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 7 个 FastAPI/Starlette 上游弃用警告。
- 全部待修复项完成后已运行 `uv run alembic upgrade head --sql`，可正常生成从空库到 `20260619_0007` 的 MySQL 迁移 SQL。
- 全部待修复项完成后已运行 `npm.cmd run lint`，通过。
- 全部待修复项完成后已运行 `npm.cmd run build`，通过；Vite 仍提示单个主 chunk 超过 500 kB 的既有体积告警。
- 全部待修复项完成后已运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml config --quiet`，通过。
- 全部待修复项完成后已运行 `git diff --check`，未发现空白或行尾问题。
- 尝试运行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml build nginx` 时，本机 Docker Desktop 未运行，无法连接 `dockerDesktopLinuxEngine`；服务器或 Docker 正常运行环境仍需执行构建并复制静态文件。
- 日志 IP 修复后已运行 `uv run ruff check app/core/request.py tests/test_request_client_ip.py`，通过。
- 日志 IP 修复后已运行 `uv run pytest tests/test_request_client_ip.py`，6 个测试通过。

## 2026-06-18

### 已完成

- 修复应用层加密会话 scope 边界：`encryption_sessions` 持久化 `scope`，后端加密会话管理器在加密响应、解密请求和登录/刷新预校验时强制匹配 `admin` / `public` scope 与允许的加密 profile。
- 公开 API 的加密响应和公开友链申请解密显式使用 `public` scope，后台 API 默认使用 `admin` scope，避免 public 加密会话被复用于后台敏感响应。
- 新增 Alembic 迁移 `20260618_0006_encryption_session_scope.py`，为 `encryption_sessions` 增加 `scope` 字段；新增回归测试覆盖 public 会话请求后台登录在认证前被拒绝。
- 新增部署脚本 `deploy/scripts/upgrade_backend_db.sh`，默认先调用 MySQL 备份脚本、构建 backend 镜像，再用一次性 backend 容器执行 `alembic upgrade head` 并输出当前迁移版本。
- 同步更新根目录 `README.md` 与 `deploy/README.md` 的维护脚本说明。

### 进行中

- 无。

### 阻塞与风险

- 本地 Windows 环境的 `bash -n deploy/scripts/upgrade_backend_db.sh` 因 WSL 未安装发行版无法完成语法检查；脚本内容已按现有 Bash 维护脚本风格编写。

### 下一步

- 继续修复安全审计中发现的后台友链/站点导航 URL 校验问题。

### 验证

- 已运行 `uv run pytest`，结果 `119 passed, 2 skipped`。
- 已运行 `uv run python -m compileall app tests`。

## 2026-06-17

### 已完成

- 新增后台友链分组和小网站导航分组 API：`GET/POST/PATCH /api/admin/friend-link-groups` 与 `GET/POST/PATCH /api/admin/site-groups`，均使用 `content-v1` 加密响应，写操作使用加密请求体、CSRF、对应后台权限和操作审计。
- 新增独立的 `LinkGroupRepository` 与 `LinkGroupService`，复用初始迁移中已有的 `friend_link_groups` 与 `site_nav_groups` 表；本次不需要新增 Alembic 迁移。
- 后台 `/admin/links` 已接入分组管理：友链和导航条目表单可选择分组，页面内可新建和编辑友链分组、导航分组；同时将友链列表/编辑逻辑拆到 `features/links/AdminFriendLinksPanel.tsx`，避免路由页面继续堆积业务逻辑。
- 小网站导航条目补齐图标、标签和打开方式编辑体验：后台表单可维护 `icon_url`、`tags_json.items`、`open_target`、可见性和排序，公开 `/sites` 卡片会展示图标与 `#标签`，点击仍走公开跳转入口统计。
- 新增 `backend/app/core/site_nav_tags.py`，统一把导航标签 JSON 规范化为 `{ "items": [...] }`，兼容旧的 `tags` 键，并限制最多 8 个标签、单个标签最多 24 个字符；本次继续复用已有 `site_nav_items.tags_json` 字段，不需要新增 Alembic 迁移。
- 新增公开小网站导航跳转入口 `GET /api/public/site-items/{item_id}/visit`：仅公开条目可访问，后端原子递增 `site_nav_items.click_count` 后记录 `public_site_item_visit` 访问日志，并 302 跳转到真实 URL；隐藏、私有或不存在的条目返回 404。
- 前台站点目录卡片改为使用公开跳转入口，点击会进入后端计数链路，同时按条目 `open_target` 决定当前页或新标签打开。
- 补充公开站点跳转接口测试，覆盖点击计数跳转成功、访问日志写入和缺失条目 404；同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md` 的小网站导航与公开 API 说明。
- 扩展真实运行库 HTTP 闭环脚本 `backend/scripts/verify_runtime_publish_flow.py` 的 M4 覆盖：新增公开友链申请、后台友链分组分配、审核通过/拒绝、公开友链展示与拒绝项排除、小网站导航分组/条目创建、图标/标签/打开方式公开展示、公开跳转 302 与点击统计，以及 `/links`、`/sites` 的桌面和移动端 Playwright 页面检查。
- 使用真实 MySQL 临时库 `blog_codex_m4_verify_20260617203644` 和临时上传目录 `backend/var/m4-verify-20260617203644` 跑通 M4 增强后的闭环脚本，输出包含 `approved_friend_link_id=1`、`rejected_friend_link_id=2`、`site_item_id=1`，并检查 `/links`、`/sites` 的 desktop/mobile 路由。
- M4 真实库验收结束后已关闭本次启动的后端 `18080` 与前端 `15173` 服务，确认 `18080`、`15173`、`14173` 均未监听；已删除临时数据库 `blog_codex_m4_verify_20260617203644` 和临时上传目录 `backend/var/m4-verify-20260617203644`。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，将真实运行库脚本覆盖范围扩展到 M4，并把下一步推进方向调整为 M5 上线前安全、部署和运维验收。
- M5 安全响应头收口：新增后端 `SecurityHeadersMiddleware`，所有响应统一设置 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy` 和 `Permissions-Policy`；生产环境额外设置 HSTS 与 Content Security Policy，本地开发环境不设置 CSP，避免影响 FastAPI `/docs`。
- 补充安全响应头测试，覆盖开发环境基础头、生产环境 HSTS/CSP 和生产环境禁用 `/docs`。
- 同步更新根目录 `README.md`、后端 `README.md`、部署 `README.md` 和 `PROJECT_PLAN.md`，记录后端与 Nginx 双层安全响应头边界。
- M5 运维脚本补齐上传文件备份/恢复：新增 `deploy/scripts/backup_uploads.sh` 和 `deploy/scripts/restore_uploads.sh`，默认备份 `/data/blog/uploads` 到 `/data/blog/backups/uploads`，恢复时必须设置 `CONFIRM_RESTORE_UPLOADS=yes`，只覆盖同名文件、不删除现有额外文件，并拒绝包含绝对路径或 `..` 的备份包。
- 新增 `blog-backup-mysql.timer` 和 `blog-backup-uploads.timer` systemd 示例，每天分别备份 MySQL 与上传文件目录；维护任务安装说明同步加入这两个 timer。
- 同步更新根目录 `README.md`、部署 `README.md` 和 `PROJECT_PLAN.md`，记录上传目录备份/恢复命令和后续运维验收方向。
- 扩展真实运行库 HTTP 闭环脚本 `backend/scripts/verify_runtime_publish_flow.py`：在原有文章发布、分类/标签、封面缩略图、正文图片渲染、公开文件短链、后台下载和访问日志覆盖基础上，新增后台创建公开页面、公开页面详情、RSS、sitemap、robots.txt、前端文章/页面 SEO 元信息、私有文件不进公开列表、后台私有文件鉴权下载、文件引用追踪、后台文章/文件列表大数量分页和桌面/移动端无横向溢出检查。
- 按用户要求创建真实 MySQL 临时库 `blog_codex_m2m3_verify_20260617184907`，迁移到 Alembic head，创建一次性后台管理员 `codex_m2m3_verify`，启动本地后端 `18080` 与前端 `15173` 后运行增强后的真实运行库闭环脚本通过；脚本输出 `post_id=12`、`post_slug=runtime-flow-verify-5617afdd`、`page_id=3`、`page_slug=runtime-flow-verify-page-1896bdf8`、`file_id=24`、`private_file_id=25`，并检查 `/admin/posts`、`/admin/files` 的 desktop/mobile 分页。
- 在同一真实临时库运行公开页分页与移动端溢出回归脚本 `backend/scripts/verify_public_page_pagination.py` 通过；脚本临时前缀为 `codex_public_pages_d056f63e`，`/links?page=2`、`/sites?page=2`、`/files?page=2` 在桌面和移动端均显示第二页分页条，`scroll_width` 等于 `client_width`，`remaining_seed_rows` 为 0。
- 真实库验收结束后已关闭本次启动的后端 `18080` 与前端 `15173` 服务，确认 `18080`、`15173`、`14173` 均未监听；已删除临时数据库 `blog_codex_m2m3_verify_20260617184907` 和临时上传目录 `backend/var/m2m3-verify-20260617184907`。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，将真实运行库脚本覆盖范围扩展到 M2/M3 验收项，并把下一步推进方向调整为 M4 友链与小网站跳转完善。
- 新增公开页分页与移动端密度回归脚本 `backend/scripts/verify_public_page_pagination.py`：脚本会向当前后端配置的运行库写入随机前缀临时友链、站点目录和公开文件，使用 Playwright/Edge 检查 `/links?page=2`、`/sites?page=2`、`/files?page=2` 在桌面和移动端视口下的分页状态与横向溢出，最后清理临时数据。
- 后端开发依赖补充 `playwright>=1.56.0`，用于运行公开页浏览器级回归脚本；脚本默认使用本机 `msedge` 通道，不下载或提交浏览器二进制。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，记录公开页分页回归脚本的启动前提、环境变量和下一步推进方向。
- 公开文章、友链、站点目录和文件列表接口补充 `total` 总数；前台友链页、站点目录页和文件页改为按真实总数显示 `第 n / m 页`，不再通过多取一条记录猜测是否存在下一页。
- 文章正文页移除可见封面区，只保留正文内容；封面仍可作为列表缩略图和分享元信息使用。
- 后台站点资料的社交入口支持添加和删除，保存、回读和公开资料接口统一最多保留 12 条；首页社交入口全部改为与邮箱一致的细线图标展示，未知平台使用柔和链接图标兜底。
- 补充公开列表总数回归测试：公开文章、友链、站点目录和公开文件接口的加密响应体均断言 `total`。
- 启动本地前后端后用 Playwright/Edge 做页面级验证：主页 GitHub/Bilibili/Email 社交入口均为 SVG 图标且无直接可见文本，文章详情 `/posts/22` 无 `.post-detail__cover` 且正文存在，临时插入大数量公开文章、友链、站点和文件后确认 `/posts` 显示 `第 1 / 6 页`、`/links` 显示 `第 1 / 2 页`、`/sites` 显示 `第 1 / 2 页`、`/files` 显示 `第 1 / 2 页`。
- 清理大数量验证数据：`codex_bulk_20260617` 和 `codex_ui_pages_20260617` 两批前缀记录最终计数均为 0，验证后关闭 Playwright 会话与本地前后端服务。
- 前台友链页、站点目录页和文件页分页状态写入 URL `page` 查询参数，刷新、分享和浏览器回退时能保持当前页。
- 收敛公开列表密度：公开紧凑行降低最小高度和上下留白，站点目录每页 6 条并压缩条目高度，长文件名、站点标题和描述允许安全换行，站点描述最多显示两行，降低数据较多时页面过长或横向溢出的风险。
- 真实运行库 HTTP 闭环验证脚本扩展分类/标签稳定 URL 回归：脚本现在会从公开分类/标签列表读取真实 slug，校验分类/标签详情接口、按 slug 筛选文章列表、sitemap 分类/标签 URL，以及前端 `/categories/{slug}`、`/tags/{slug}` 路由可访问性。
- 使用本地运行库和已启动的前后端服务跑通扩展后的验证脚本，结果为 `post_id=14`、`post_slug=runtime-flow-verify-0aae62a0`、`file_id=10`、`category_slug=category-80144e2e73b1`、`tag_slug=seo`。
- 本次真实运行库验证创建了临时后台账号 `codex_verify_routes_20260617130311`；验证后已撤销刷新令牌、移除角色、禁用账号并重置随机密码，避免留下可用后台入口。
- 同步更新根目录 `README.md` 和后端 `README.md`，记录真实运行库脚本现在需要前后端服务，以及 `BLOG_VERIFY_FRONTEND_URL` 配置。
- 前台归档筛选的分类与标签列表改为按公开文章数量降序展示前 5 项，避免分类/标签过多时撑高筛选区。
- 分类与标签剩余项收敛到 `...` 按钮，点击后在模态框中分页浏览，每页 12 项，并保持分类/标签稳定公开 URL 跳转。
- 新增公开分类详情接口 `GET /api/public/categories/{slug}` 和公开标签详情接口 `GET /api/public/tags/{slug}`，均使用 public scope `content-v1` 加密响应，只返回已公开且已到发布时间文章实际使用到的分类/标签，并在 200/404 时写入访问日志。
- sitemap 扩展分类与标签稳定入口，除首页、文章列表和文章详情外，现在会包含 `/categories/{slug}` 与 `/tags/{slug}`，访问日志 `count` 同步统计文章、分类和标签 URL 数量。
- 前端新增 `/categories/:slug` 与 `/tags/:slug` 公开路由，和 `/posts` 共用 `PublicPostArchivePage` 归档视图，分类/标签筛选 chip 改为稳定链接，分页继续通过 `page` 查询参数维护。
- 前端文章归档请求封装补充 `getPublicCategory` 与 `getPublicTag`，分类/标签独立页会读取详情用于标题、SEO 和缺失入口提示。
- 同步更新根目录 `README.md`、后端 `README.md`、前端 `README.md` 和 `PROJECT_PLAN.md`，记录分类/标签稳定 URL、API 和 sitemap 范围。
- 公开文章列表接口 `GET /api/public/posts` 新增 `category={slug}` 和 `tag={slug}` 查询参数，按分类、标签 slug 筛选公开且已到发布时间的文章，并在访问日志 `detail_json` 中记录筛选条件。
- 前台 `/posts` 接入归档筛选入口：读取公开分类与标签聚合接口，筛选状态写入 URL 查询参数，分页状态使用 `page` 查询参数，切换筛选时自动回到第一页。
- 文章列表页补充“归档筛选”紧凑筛选区，分类和标签使用可换行的细边框按钮，移动端降级为单列，筛选结果为空时显示筛选空状态。
- 同步更新后端 `README.md` 和 `PROJECT_PLAN.md`，记录公开文章列表筛选参数，并将下一步推进到分类/标签独立公开路由与 sitemap 扩展。
- 根目录 `README.md` 调整说明顺序，新增“从 Git 开始”作为第一节，先说明 clone、切换 `dev`、同步远端、提交前检查、提交推送和 `main` 快进流程，再进入架构、功能和开发部署说明。
- 根目录 `README.md` 补充稳定功能模块说明，覆盖文章发布、页面、文件、友链、小网站导航、站点设置、后台管理、公开订阅 SEO 和运维任务，避免只讲架构不讲系统能力。
- 调整 `deploy/README.md` 为部署目录补充说明，只保留 Compose、环境变量模板、Nginx、维护脚本和 systemd timer 的文件职责与注意事项，完整部署流程仍由根目录 `README.md` 承担。
- 重写根目录 `README.md`：移除当前阶段流水账和过长功能状态描述，改为面向开发者的项目架构、本地开发、配置、数据库迁移、验证、生产部署、运维任务、备份恢复和文档分工说明。
- 明确 `README.md` 与 `PROJECT_PROGRESS.md` 的职责边界：README 维护稳定开发与部署入口，具体实现进展、风险和下一步继续放在进度记录中。
- 新增公开分类接口 `GET /api/public/categories`，使用 public scope `content-v1` 加密响应，按已公开且已到发布时间的文章聚合分类并返回 `id`、`name`、`slug` 和 `post_count`。
- 新增公开标签接口 `GET /api/public/tags`，使用同一公开文章过滤口径聚合标签并返回公开文章数量，避免草稿、私密文章和未到点定时文章进入前台归档数据。
- `ContentRepository` 收敛公开文章过滤条件，公开文章列表、详情、RSS/sitemap feed、分类聚合和标签聚合复用同一发布可见性规则。
- 前端 `features/posts` 补充 `PublicTaxonomyItem` 类型和 `listPublicCategories`、`listPublicTags` 请求封装，供下一步前台归档筛选入口复用。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，记录公开分类/标签接口字段、加密响应方式和下一步前台归档筛选计划。
- 新增前端公开页面 SEO hook `usePageSeo`，统一维护 `document.title`、`description`、`keywords`、canonical 和基础 Open Graph 元信息。
- 移除 `PublicLayout` 对 `document.title` 的全局覆盖，避免公开子页面设置的页面级标题被站点标题覆盖。
- 首页、文章列表、文章详情、友链、文件和站点目录已接入 `usePageSeo`；文章详情使用文章 SEO 标题/描述/关键词、canonical URL、`og:type=article` 和封面图作为分享元信息。
- `frontend/index.html` 新增默认 description 与基础 Open Graph 兜底，前端默认 RSS 入口从 `/feed` 调整为 `/rss.xml`。
- 同步更新根目录 `README.md`、前端 `README.md` 和 `PROJECT_PLAN.md`，记录公开页面 canonical/Open Graph 基线，并将下一步调整为公开分类与标签接口。
- 新增 `GET /robots.txt` 根级公开端点，不要求应用层加密会话；默认允许常规公开内容抓取，屏蔽 `/admin` 与 `/api/admin/`，并声明由 `BLOG_PUBLIC_BASE_URL` 生成的 `/sitemap.xml` 绝对地址。
- `robots.txt` 访问会写入 `access_logs`，记录为 `public_robots`。
- 生产 Nginx 站点模板新增根级 `/rss.xml`、`/sitemap.xml`、`/robots.txt` 精确反代规则，避免公开 SEO 文件被前端 SPA `index.html` 兜底吞掉。
- 同步更新根目录 `README.md`、后端 `README.md`、部署 `README.md` 和 `PROJECT_PLAN.md`，记录 robots.txt 与 Nginx 反代规则，并将下一步调整为公开页面 canonical 与 Open Graph 元信息基线。
- 重新设计公开文章列表分类标签 UI：顶部状态旁展示分类归属，摘要下方使用低对比 `#标签` 注脚，不再显示“分类 / 标签”字段名前缀。
- 公开文章列表会过滤“定时发布”这类发布流程词，避免把验证用发布语义当作前台内容标签展示。
- 补充分类小圆点、标签细下划线与 hover 状态，保持移动端和桌面端都能自然换行。
- 新增根级公开 XML 端点 `GET /rss.xml` 与 `GET /sitemap.xml`，不要求应用层加密会话，方便订阅客户端和搜索引擎直接抓取。
- RSS 2.0 输出站点标题、站点描述、文章永久链接、发布时间、SEO 标题、SEO 描述、分类和标签；站点信息来自公开 `site_profile`。
- sitemap 输出首页、文章列表页和已公开文章永久链接，使用文章更新时间或发布时间生成 `lastmod`。
- 新增 `ContentRepository.list_public_feed_posts` 与 `ContentService.list_public_feed_posts`，复用公开文章过滤规则，仅包含未删除、公开可见、已发布或已到点定时发布的文章。
- RSS 和 sitemap 访问会写入 `access_logs`，分别记录为 `public_rss` 与 `public_sitemap`。
- 默认站点资料中的 RSS 社交入口从 `/feed` 调整为 `/rss.xml`。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，记录 RSS/sitemap 初版和后续 `robots.txt` 计划。
- 新增友链状态检查服务 `FriendLinkHealthService`，只检查已通过友链，按最久未检查优先排序，写入 `last_checked_at` 与 `last_status_code`。
- 新增友链状态检查任务 `backend/app/tasks/links.py` 和 CLI 子命令 `uv run python -m app.cli check-friend-links --limit 100 --timeout-seconds 5`；任务优先使用 `HEAD`，遇到 `405` 时回退 `GET`，访问失败记录为状态码 `0`。
- 后台友链列表和详情开始展示“未检查 / 正常 / 异常 / 访问失败”与最近检查时间，方便人工判断是否需要下架或修正。
- 新增 `deploy/systemd/blog-check-friend-links.service` 与 `.timer`，生产示例默认每天 04:40 检查已通过友链，并同步更新部署说明。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，记录友链状态检查 CLI、systemd timer 和后续 RSS/sitemap 计划。
- 新增公开友链申请接口 `POST /api/public/friend-links/applications`：请求体使用 public scope `content-v1` 加密，后端校验站点 URL、头像 URL 和 RSS URL 仅允许 `http/https`，固定创建 `pending` 状态友链。
- 公开友链申请入口接入现有限流服务，默认 `BLOG_FRIEND_LINK_APPLICATION_RATE_LIMIT_MAX_ATTEMPTS=5`、`BLOG_FRIEND_LINK_APPLICATION_RATE_LIMIT_WINDOW_SECONDS=600`，命中返回 `429` 并写入 `security_events`。
- 前台 `/links` 新增友链申请表单，可提交站点名称、URL、头像 URL、RSS URL 和描述；提交成功后显示审核提示，公开列表仍只展示已通过友链。
- 公开友链申请会写入 `access_logs`，后台友链审核列表可继续接住 `pending` 记录并审核通过或拒绝。
- 同步更新根目录 `README.md`、后端 `README.md`、`PROJECT_PLAN.md` 和环境变量示例，记录公开友链申请、限流配置和后续状态检查任务。
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
- 使用本机真实 MySQL 临时库 `blog_codex_cleanup_verify` 和临时上传目录 `backend/var/codex-cleanup-verify` 验证服务层文件清理闭环：Alembic 迁移到 head、上传公开图片、软删除并清理物理文件、制造孤儿文件、dry-run 不删除、显式删除孤儿文件。
- 使用本机真实 MySQL 临时库 `blog_codex_cleanup_cli_verify` 和临时上传目录 `backend/var/codex-cleanup-cli-verify` 验证 CLI 文件清理闭环：`cleanup-deleted-files` 删除 1 条软删记录和 1 个物理文件，`cleanup-orphan-files` dry-run 只汇总 1 个孤儿文件，`cleanup-orphan-files --delete` 删除 1 个孤儿文件。
- 两轮真实库验证结束后均删除临时数据库和临时上传目录；已确认 `blog_codex_cleanup_cli_verify` 不存在，`backend/var/codex-cleanup-cli-verify` 不存在。
- 新增 Redis 共享限流适配器：`RateLimitService` 改为接收后端协议，保留 `InMemoryRateLimiter`，新增 `RedisRateLimiter`，使用 Redis sorted set 与 Lua 脚本完成原子滑动窗口检查。
- 新增限流配置 `BLOG_RATE_LIMIT_BACKEND`、`BLOG_REDIS_URL`、`BLOG_REDIS_KEY_PREFIX`；本地默认 `memory`，生产环境示例默认 `redis://redis:6379/0`，继续只在 Docker 私有网络访问 Redis。
- Redis 适配器在连接异常时会按同一限流 key 回落到进程内限流器，避免 Redis 短暂不可用导致后台登录或加密协商入口完全失去保护。
- 补充 Redis 限流单元测试，覆盖共享窗口拦截和 Redis 异常时的内存降级。
- 同步更新根目录 `README.md`、后端 `README.md`、`PROJECT_PLAN.md` 和环境变量示例，标记 Redis 共享限流适配器已接入。
- 新增 `deploy/systemd` 维护任务调度示例，包含过期加密会话清理、软删除文件清理和孤儿文件 dry-run 扫描的 service/timer。
- 调度建议为：过期加密会话每小时清理；软删除文件每天 03:20 清理超过 7 天、无引用且路径安全的文件；孤儿文件每周日 04:10 只 dry-run 扫描，真实删除仍需人工确认后显式执行 `--delete`。
- 同步更新根目录 `README.md`、后端 `README.md`、部署 `README.md` 和 `PROJECT_PLAN.md`，记录 systemd timer 安装方式、默认部署路径 `/opt/blog` 和孤儿文件人工删除要求。
- 新增真实 Redis 集成测试 `tests/test_rate_limit_redis_integration.py`，默认未设置 `BLOG_TEST_REDIS_URL` 时跳过；设置后会验证后台加密协商入口和后台登录入口在 Redis 共享限流后端下返回 429、携带 `Retry-After` 并记录安全事件。
- 将 Redis 客户端初始化显式设置为 RESP2 协议，兼容本次临时 Windows Redis 5 和生产 Docker Redis 7。
- 由于 Docker Desktop daemon 未运行且本机 `wsl --update` 返回 403，本次改用一次性下载的 Windows Redis `v5.0.14.1` zip 在 `127.0.0.1:16379` 验证真实 Redis 集成测试；验证后已关闭 Redis 进程并删除临时目录。
- 新增真实运行库 HTTP 级闭环验证脚本 `backend/scripts/verify_runtime_publish_flow.py`，覆盖后台 `sensitive-v1` 加密登录、`content-v1` 上传公开图片、后台文章实时预览、创建并发布文章、公开文章列表与详情、封面缩略图、正文图片签名渲染、公开文件栏临时链接下载、后台鉴权下载和后台访问日志查询。
- 脚本默认从 `BLOG_VERIFY_ADMIN_USERNAME`、`BLOG_VERIFY_ADMIN_PASSWORD` 和 `BLOG_VERIFY_BASE_URL` 读取验证环境，验证完成后默认把测试文章归档，避免长期占用公开文章列表；传入 `--keep-published` 可保留公开状态。
- 使用真实运行库 `blog_codex_runtime` 跑通闭环验证，结果为 `post_id=9`、`post_slug=runtime-flow-verify-50d3b1ca`、`file_id=10`，并确认访问日志包含 `admin_file_download`、`post_image_render`、`post_image_thumbnail`、`public_file_download`、`public_file_temporary_url`、`public_post_detail` 和 `public_posts_list`。
- 本次为真实运行库验证创建了临时后台账号 `codex_verify_20260617`；验证后因测试文章作者外键引用不能直接删除用户，已撤销刷新令牌、移除角色、禁用账号并重置为随机密码，避免留下可用后台入口。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，记录真实运行库闭环验证脚本，并按用户纠偏将下一步拉回“真实前端写作发布闭环”这一核心目标。
- 补齐文章发布核心元数据：新增 `posts.seo_keywords` Alembic 迁移，后台文章表单可填写定时发布时间、分类、标签、SEO 标题、SEO 描述和 SEO 关键词。
- 后端文章创建/更新会自动创建缺失的分类和标签，并维护 `post_categories`、`post_tags` 关联；后台和公开文章响应都会返回 `category_names`、`tag_names` 与 `seo_keywords`。
- 定时发布语义已落地：`status=scheduled` 且 `published_at` 晚于当前时间的文章不会出现在公开列表和详情；到点后公开查询可见。
- 前台文章列表和详情开始展示分类与标签；文章详情会使用 SEO 标题、描述和关键词更新浏览器标题、`description` 与 `keywords` meta。
- 真实运行库验证脚本扩展为覆盖分类、标签、SEO 信息和未来定时文章不提前公开；使用真实运行库再次跑通，结果为 `post_id=12`、`post_slug=runtime-flow-verify-7b7986d2`、`file_id=10`。
- 本次真实运行库验证创建了临时后台账号 `codex_verify_article_20260617`；验证后已归档 `runtime-flow-verify%` 验证文章、撤销刷新令牌、移除角色、禁用账号并重置随机密码。
- 同步更新根目录 `README.md`、后端 `README.md` 和 `PROJECT_PLAN.md`，标记文章定时发布、分类、标签和 SEO 信息已完成，并将下一步调整为用户指定的友链管理。
- 补齐 M1 操作审计闭环：`LogService` 与 `LogRepository` 新增 `record_audit_log`，后台文章、页面、文件、友链、导航和设置的关键写操作会写入 `audit_logs`，记录操作者、动作、实体、IP、UA 和最小变更摘要，不记录正文、密钥、Token 或完整设置值。
- 前端后台日志页新增“操作”标签，接入 `/api/admin/audit-logs`，现在可在同一日志页查看操作审计、访问日志、登录日志和安全事件。
- 同步更新后端 `README.md` 和 `PROJECT_PLAN.md`，将 M1 认证与后台框架阶段标记为已完成，后续进入 M2 文章与页面、M3 文件管理的收尾验收。
- 补齐 M2 公开页面详情链路：新增 `GET /api/public/pages/{slug}`，只返回 `status=published` 且未软删除的独立页面，草稿、归档、未发布或不存在页面返回 404，并写入 `access_logs`。
- 前端新增公开独立页面路由 `/:slug` 和 `PageDetailPage`，复用 `MathHtml` 与 `usePageSeo` 展示后台发布的关于、项目等页面；该路由放在 `/posts`、`/links`、`/files`、`/sites` 等固定前台路由之后，避免抢占系统入口。
- 同步更新后端 `README.md`、前端 `README.md` 和 `PROJECT_PLAN.md`，记录公开页面 API、前端路由顺序和 M2 下一步验收方向。

### 进行中

- M1 认证与后台框架已完成；M2 文章与页面、M3 文件管理、M4 友链与小网站跳转已完成真实 MySQL 临时库闭环验收。M5 已补齐后端安全响应头兜底和上传文件备份/恢复脚本，当前继续进行部署验收和上线前检查清单整理。

### 阻塞与风险

- 若前端页面仍保留旧 bundle 或旧 dev server 状态，需刷新页面后再保存文章；后端已重启到当前代码。
- 实际执行 `cleanup-encryption-sessions` 会删除当前配置数据库里的过期会话记录；本次仅验证 CLI 子命令可见性和业务方法测试，未在未确认目标库的情况下直接运行清理命令。
- 后台文件下载接口返回文件流，不走 `content-v1` 加密信封；安全边界依赖后台 HttpOnly Cookie 或 Bearer Token 鉴权、`file:upload` 权限和后端路径校验。
- 实际执行 `cleanup-deleted-files` 会删除当前配置数据库中的软删记录和本地物理文件；本次只跑服务层单元测试和 CLI 可见性检查，未在未确认目标库与上传目录的情况下直接运行清理命令。
- `cleanup-orphan-files` 默认 dry-run 不删除文件；显式加 `--delete` 会删除当前配置上传目录中的孤儿文件，本次未在未确认目标库与上传目录的情况下执行真实删除。
- 本次真实清理验证仅使用 `blog_codex_cleanup_verify`、`blog_codex_cleanup_cli_verify` 和对应临时上传目录，未触碰当前运行库 `blog_codex_runtime`；MySQL 对重复 `DROP DATABASE IF EXISTS` 输出过一次“database doesn't exist”提示，但最终复查临时库和临时目录均不存在。
- systemd timer 示例默认 `WorkingDirectory=/opt/blog`，如果实际部署目录不同，安装前必须修改 `deploy/systemd/*.service`；孤儿文件 timer 只 dry-run，不自动执行 `--delete`。
- Docker Desktop daemon 当前不可用，`wsl --update` 返回 403；本次已用临时 Windows Redis 完成真实 Redis 联调，后续若要验证 Docker Compose 私有 Redis，需要先修复 Docker/WSL 环境。
- 真实运行库闭环验证会创建测试文章、页面、上传文件、友链申请和导航数据；脚本默认会把测试文章和页面归档、把验证友链改为拒绝并隐藏验证导航分组/条目，但上传文件与访问日志会保留，后续如需清理应先确认是否仍被 `file_usages` 引用。
- 本次运行库验证中复用了同一张验证图片文件 `file_id=10`；验证文章已归档，但验证图片和访问日志保留，后续文件清理前需要确认引用状态。
- 公开友链申请入口已接入应用限流，但公开加密会话协商仍会先发生；若后续遇到明显垃圾申请，需要继续评估验证码、黑名单或更细粒度的 URL 去重策略。
- `check-friend-links` 会访问外部站点，可能受网络波动、对方反爬、HEAD 支持不完整或临时 5xx 影响；本任务只记录状态码和失败，不自动修改人工审核状态。
- 公开站点导航图标当前使用外部 `icon_url` 直接加载，若对方站点防盗链、图标失效或网络不可达，前台只会缺失图标，不影响标题、描述、标签和跳转。
- RSS 与 sitemap 当前直接实时查询数据库生成 XML，适合当前规模；后续文章量明显增大或搜索引擎抓取频率升高时，再评估缓存或后台任务刷新静态文件。
- `/rss.xml`、`/sitemap.xml` 与 `/robots.txt` 的绝对链接依赖 `BLOG_PUBLIC_BASE_URL`，生产部署前必须确认该值为公网 HTTPS 域名。
- 生产 Nginx 已补充根级 SEO 文件反代规则；后续如果改为静态预渲染或 CDN 缓存，需要同步检查这些路径是否仍返回后端生成内容或等价静态文件。
- 当前 canonical 与 Open Graph 由 React 客户端运行时写入，能改善浏览器内分享状态，但对不执行 JavaScript 的搜索引擎或社交抓取器仍不如 SSR/SSG；后续若 SEO 要求提高，需要评估预渲染或服务端渲染。
- 分类/标签稳定 URL、公开友链页和公开站点目录页已纳入真实运行库 HTTP 验证脚本；脚本默认还会请求前端 `15173`，如果只启动后端而未启动前端，需通过 `BLOG_VERIFY_FRONTEND_URL` 指向可访问的前端站点，或先启动前端开发服务。
- 公开页分页回归脚本会向当前配置数据库写入临时友链、站点目录和公开文件；脚本已在 `finally` 中清理随机前缀数据，但如果进程被系统强杀，需用输出的 `prefix` 检查并手动清理残留记录。
- 公开页分页回归脚本默认使用 Playwright 的 `msedge` 通道；若运行环境没有 Edge，需要通过 `BLOG_VERIFY_BROWSER_CHANNEL` 指向可用 Chromium 通道，或先安装对应浏览器运行时。

### 下一步

- M5 部署验收：复查 Docker Compose、Nginx、环境变量示例、systemd 维护任务和生产端口暴露策略，确认公网只暴露 Nginx `80/443`。
- M5 上线前检查清单：把证书续期、备份外传、恢复演练、迁移前备份、维护任务 timer 和公网入口检查整理为可执行清单。

### 验证

- 友链和导航分组管理接入后已运行 `uv run ruff check app tests/test_admin_links_api.py`，通过。
- 友链和导航分组管理接入后已运行 `uv run pytest tests/test_admin_links_api.py tests/test_public_content_api.py`，35 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 友链和导航分组管理接入后已运行 `npm.cmd run lint`，通过。
- 友链和导航分组管理接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 友链和导航分组管理接入后已运行 `git diff --check`，未发现空白或行尾问题。
- 小网站导航点击统计接入后已运行 `uv run pytest tests/test_public_content_api.py tests/test_admin_links_api.py`，29 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- 小网站导航点击统计接入后已运行 `npm.cmd run lint`，通过。
- 导航图标/标签编辑接入后已运行 `uv run ruff check app tests/test_admin_links_api.py tests/test_public_content_api.py`，通过。
- 导航图标/标签编辑接入后已运行 `uv run pytest tests/test_admin_links_api.py tests/test_public_content_api.py`，36 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告和一次 `HTTP_422_UNPROCESSABLE_ENTITY` 常量弃用提示。
- 导航图标/标签编辑接入后已运行 `npm.cmd run lint`，通过。
- 导航图标/标签编辑接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 真实运行库脚本扩展后已运行 `uv run ruff check scripts\verify_runtime_publish_flow.py`，通过。
- 真实运行库脚本扩展后已运行 `uv run python scripts\verify_runtime_publish_flow.py --help`，通过。
- 已创建真实 MySQL 临时库 `blog_codex_m2m3_verify_20260617184907`，设置临时上传目录 `backend/var/m2m3-verify-20260617184907`，运行 `uv run alembic upgrade head`，从空库迁移到 `20260617_0005`。
- 已在真实临时库创建一次性后台管理员 `codex_m2m3_verify`，启动本地后端 `uv run python main.py` 与前端 `npm.cmd run dev -- --host 127.0.0.1 --port 15173`，后端 `/healthz` 返回 200，前端首页返回 200。
- 已在真实临时库运行增强后的 `uv run python scripts\verify_runtime_publish_flow.py --timeout 30`，通过；覆盖后台创建页面、公开页面访问、文章发布、分类/标签、RSS、sitemap、robots.txt、前端 SEO 元信息、公开/私有文件访问、文件引用追踪、后台文章/文件列表分页和访问日志。
- 已在真实临时库运行 `uv run python scripts\verify_public_page_pagination.py --timeout 30`，通过；`/links?page=2`、`/sites?page=2`、`/files?page=2` 在 desktop/mobile 视口均无横向溢出，临时种子数据清理后 `remaining_seed_rows` 为 0。
- 真实库验收结束后已停止本次启动的后端与前端服务，确认 `18080`、`15173`、`14173` 均未监听；已删除临时数据库与临时上传目录。
- M4 友链/导航脚本扩展后已运行 `uv run ruff check scripts\verify_runtime_publish_flow.py`，通过。
- M4 友链/导航脚本扩展后已运行 `uv run python scripts\verify_runtime_publish_flow.py --help`，通过。
- 已创建真实 MySQL 临时库 `blog_codex_m4_verify_20260617203644`，设置临时上传目录 `backend/var/m4-verify-20260617203644`，迁移到 Alembic head，并创建一次性后台管理员 `codex_m4_verify_20260617203644`。
- 已在真实临时库运行 M4 增强后的 `uv run python scripts\verify_runtime_publish_flow.py --timeout 30`，通过；输出包含 `post_id=1`、`post_slug=runtime-flow-verify-b1ec6808`、`page_id=1`、`page_slug=runtime-flow-verify-page-924f64e4`、`file_id=1`、`private_file_id=2`、`approved_friend_link_id=1`、`rejected_friend_link_id=2`、`site_item_id=1`。
- 本次 M4 真实库验收检查了 `/links:desktop`、`/sites:desktop`、`/links:mobile`、`/sites:mobile`，访问日志类型包含 `public_friend_link_application`、`public_friend_links_list`、`public_site_items_list` 和 `public_site_item_visit`。
- M4 真实库验收结束后已停止本次启动的后端与前端服务，确认 `18080`、`15173`、`14173` 均未监听；已删除临时数据库 `blog_codex_m4_verify_20260617203644` 和临时上传目录 `backend/var/m4-verify-20260617203644`。
- 本次 M4 脚本与文档收口后已运行 `git diff --check`，未发现空白或行尾问题；并再次确认 `18080`、`15173`、`14173` 均未监听。
- M5 安全响应头接入后已运行 `uv run ruff check app\core\security.py tests\test_admin_security.py`，通过。
- M5 安全响应头接入后已运行 `uv run pytest tests\test_admin_security.py tests\test_health.py`，13 个测试通过；仍存在 FastAPI/Starlette TestClient 上游弃用警告。
- M5 安全响应头接入后已运行后端全量 `uv run ruff check .`，通过。
- M5 安全响应头接入后已运行后端全量 `uv run pytest`，115 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient、cookies 和 `HTTP_422_UNPROCESSABLE_ENTITY` 上游弃用警告。
- 上传文件备份/恢复脚本接入后已运行 Git Bash `bash -n deploy/scripts/backup_mysql.sh deploy/scripts/restore_mysql.sh deploy/scripts/backup_uploads.sh deploy/scripts/restore_uploads.sh deploy/scripts/renew_cert.sh`，通过。
- 上传文件备份/恢复脚本接入后已用临时目录执行 smoke test：写入 `uploads/public/example.txt`，运行 `backup_uploads.sh` 生成 tar.gz，再用 `CONFIRM_RESTORE_UPLOADS=yes restore_uploads.sh` 恢复到独立目录并校验文件内容，临时目录已清理。
- 备份 systemd 示例接入后已运行文本结构检查，确认 `blog-backup-mysql.timer` 指向 `blog-backup-mysql.service`、`blog-backup-uploads.timer` 指向 `blog-backup-uploads.service`，两个 service 均包含 `WorkingDirectory=/opt/blog` 和对应备份脚本命令。
- M5 部署验收已运行 `docker compose -f deploy\docker-compose.yml -f deploy\docker-compose.prod.yml config --quiet`，通过。
- M5 部署端口结构已运行文本检查，确认生产 Compose 只映射 Nginx `80:80` 与 `443:443`，`backend`、`mysql`、`redis` 未配置宿主端口映射。
- 本次 M2/M3 验收脚本与文档更新后已运行后端全量 `uv run ruff check .`，通过。
- 本次 M2/M3 验收脚本与文档更新后已运行后端全量 `uv run pytest`，104 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 和 cookies 相关上游弃用警告。
- 本次 M2/M3 验收脚本与文档更新后已运行 `npm.cmd run lint`，通过。
- 本次 M2/M3 验收脚本与文档更新后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 操作审计闭环补齐后已运行 `uv run ruff check app tests\test_admin_logs_api.py tests\test_admin_content_api.py tests\test_admin_files_api.py tests\test_admin_links_api.py tests\test_admin_settings_api.py`，通过。
- 操作审计闭环补齐后已运行 `uv run pytest tests\test_admin_logs_api.py tests\test_admin_content_api.py tests\test_admin_files_api.py tests\test_admin_links_api.py tests\test_admin_settings_api.py`，31 个测试通过；仍存在 FastAPI/Starlette TestClient 和 cookies 相关上游弃用警告。
- 操作审计闭环补齐后已运行 `npm.cmd run lint`，通过。
- 操作审计闭环补齐后已运行后端全量 `uv run ruff check .`，通过。
- 操作审计闭环补齐后已运行后端全量 `uv run pytest`，102 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 和 cookies 相关上游弃用警告。
- 操作审计闭环补齐后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 操作审计闭环补齐后已运行 `git diff --check`，未发现空白或行尾问题。
- 公开页面详情链路接入后已运行 `uv run ruff check app tests\test_public_content_api.py`，通过。
- 公开页面详情链路接入后已运行 `uv run pytest tests\test_public_content_api.py`，20 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 公开页面详情路由接入后已运行 `npm.cmd run lint`，通过。
- 公开页面详情链路接入后已运行后端全量 `uv run ruff check .`，通过。
- 公开页面详情链路接入后已运行后端全量 `uv run pytest`，104 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 和 cookies 相关上游弃用警告。
- 公开页面详情路由接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 公开页面详情链路接入后已运行 `git diff --check`，未发现空白或行尾问题。
- 公开页分页回归脚本新增后已运行 `uv run ruff check scripts\verify_public_page_pagination.py`，通过。
- 公开页分页回归脚本新增后已运行 `uv run python scripts\verify_public_page_pagination.py --help`，通过。
- 已启动本地后端 `uv run python main.py` 和前端 `npm.cmd run dev -- --host 127.0.0.1 --port 15173`，运行 `uv run python scripts\verify_public_page_pagination.py` 通过；脚本输出 `/links?page=2` 桌面/移动端均为 `第 2 / 3 页`，`/sites?page=2` 桌面/移动端均为 `第 2 / 3 页`，`/files?page=2` 桌面/移动端均为 `第 2 / 2 页`，所有视口 `scroll_width` 等于 `client_width`，`remaining_seed_rows` 为 0。
- 公开页分页回归脚本新增后已运行后端全量 `uv run ruff check .`，通过。
- 公开页分页回归脚本新增后已运行后端全量 `uv run pytest`，101 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 和 cookies 相关上游弃用警告。
- 公开页分页回归脚本新增后已运行 `npm.cmd run lint`，通过。
- 公开页分页回归脚本新增后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 前台友链/站点/文件页服务端分页接入后已运行 `npm.cmd run lint`，通过。
- 前台友链/站点/文件页服务端分页接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 前台友链/站点/文件页服务端分页接入后已启动本地前后端，通过浏览器检查 `/links`、`/sites`、`/files` 均加载完成且无横向溢出；验证结束后已关闭本次启动的服务，并确认 `18080`、`15173`、`14173` 均未监听。
- 真实运行库 HTTP 闭环脚本扩展后已运行 `uv run ruff check scripts\verify_runtime_publish_flow.py`，通过。
- 真实运行库 HTTP 闭环脚本扩展后已运行 `uv run python scripts\verify_runtime_publish_flow.py --help`，通过。
- 真实运行库 HTTP 闭环脚本扩展后已使用本地运行库和本次已启动的前后端服务执行 `uv run python scripts\verify_runtime_publish_flow.py`，通过；验证文章默认归档，临时后台账号已禁用并撤权。
- 分类与标签筛选溢出收敛后已运行 `npm.cmd run lint`，通过。
- 分类与标签筛选溢出收敛后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 分类与标签独立公开路由接入后已运行 `uv run ruff check app tests\test_public_content_api.py`，通过。
- 分类与标签独立公开路由接入后已运行 `uv run pytest tests\test_public_content_api.py`，18 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 分类与标签独立公开路由接入后已运行后端全量 `uv run pytest`，101 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 和 cookies 相关上游弃用警告。
- 分类与标签独立公开路由接入后已运行 `npm.cmd run lint`，通过。
- 分类与标签独立公开路由接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 前台归档筛选入口接入后已运行 `uv run ruff check .`，通过。
- 前台归档筛选入口接入后已运行 `uv run pytest tests\test_public_content_api.py tests\test_content_service.py`，21 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 前台归档筛选入口接入后已运行后端全量 `uv run pytest`，97 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 相关上游弃用警告。
- 前台归档筛选入口接入后已运行 `npm.cmd run lint`，通过。
- 前台归档筛选入口接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 前台归档筛选入口接入后已运行 `git diff --check`，未发现空白或行尾问题。
- README Git 入口调整后已运行 `git diff --check`，未发现空白或行尾问题。
- 根目录 README 功能说明与 `deploy/README.md` 职责收敛后已运行 `git diff --check`，未发现空白或行尾问题。
- README 开发者文档重写后已运行 `git diff --check`，未发现空白或行尾问题。
- 公开分类与标签接口接入后已运行 `uv run ruff check .`，通过。
- 公开分类与标签接口接入后已运行 `uv run pytest tests\test_public_content_api.py tests\test_content_service.py`，20 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 公开分类与标签接口接入后已运行后端全量 `uv run pytest`，96 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 相关上游弃用警告。
- 公开分类与标签前端 API 封装接入后已运行 `npm.cmd run lint`，通过。
- 公开分类与标签前端 API 封装接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 公开页面 canonical/Open Graph 基线接入后已运行 `npm.cmd run lint`，通过。
- 公开页面 canonical/Open Graph 基线接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- robots.txt 与 Nginx SEO 反代接入后已运行 `uv run ruff check .`，通过。
- robots.txt 与 Nginx SEO 反代接入后已运行 `uv run pytest tests\test_public_content_api.py tests\test_content_service.py`，18 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- robots.txt 与 Nginx SEO 反代接入后已运行 `docker compose -f deploy\docker-compose.yml -f deploy\docker-compose.prod.yml config --quiet`，通过。
- 公开文章列表分类标签展示调整后已运行 `npm.cmd run lint`，通过。
- 公开文章列表分类标签展示调整后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- RSS/sitemap 初版接入后已运行 `uv run ruff check .`，通过。
- RSS/sitemap 初版接入后已运行 `uv run pytest tests\test_public_content_api.py tests\test_content_service.py`，17 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 友链状态检查任务接入后已运行 `uv run ruff check .`，通过。
- 友链状态检查任务接入后已运行 `uv run pytest tests\test_link_health.py tests\test_admin_links_api.py`，9 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 友链状态检查任务接入后已运行后端全量 `uv run pytest`，91 个测试通过、2 个 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 相关上游弃用警告。
- 友链状态检查任务接入后已运行 `uv run python -m app.cli --help`，确认 `check-friend-links` 子命令已注册。
- 友链状态检查后台展示接入后已运行 `npm.cmd run lint`，通过。
- 友链状态检查后台展示接入后已运行 `npm.cmd run build`，通过；仍存在 KaTeX 引入后的 Vite 主 chunk 超过 500KB 提示。
- 友链状态检查 systemd 示例接入后已运行文本结构检查，确认 service 包含 `WorkingDirectory=/opt/blog` 与 `check-friend-links` 命令，timer 指向 `blog-check-friend-links.service` 并包含 `OnCalendar`。
- 公开友链申请入口新增后已运行 `uv run ruff check .`，通过。
- 公开友链申请入口新增后已运行 `uv run pytest tests\test_public_content_api.py tests\test_admin_links_api.py tests\test_rate_limit.py`，20 个测试通过；仍存在 FastAPI TestClient 依赖的上游弃用警告。
- 公开友链申请入口新增后已运行 `uv run pytest`，89 个测试通过、2 个 Redis 集成测试因未配置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI/Starlette TestClient 相关上游弃用警告。
- 公开友链申请表单新增后已运行 `npm.cmd run lint`，通过。
- 公开友链申请表单新增后已运行 `npm.cmd run build`，通过。
- 公开友链申请入口新增后已运行 `git diff --check`，未发现空白或行尾问题。
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
- 真实运行库闭环验证脚本新增后已运行 `uv run ruff check .`，通过。
- 已运行 `uv run python scripts/verify_runtime_publish_flow.py --help`，确认脚本参数说明可正常输出。
- 已运行 `uv run alembic upgrade head`，真实运行库迁移状态已到最新。
- 已启动本地后端 `uv run python main.py`，确认 `http://127.0.0.1:18080/healthz` 返回 200 后运行真实运行库闭环验证脚本，脚本返回 `ok: true`。
- 真实运行库闭环验证结束后已关闭本次启动的后端服务，并确认 `18080`、`15173`、`14173` 均无监听。
- 已清理本次真实运行库验证使用的临时后台账号权限：撤销刷新令牌、移除角色、禁用账号并重置随机密码。
- 已运行 `uv run pytest tests\test_admin_content_api.py tests\test_admin_files_api.py tests\test_public_content_api.py tests\test_admin_logs_api.py`，28 个测试通过；仍存在 FastAPI TestClient 与 Starlette TestClient cookies 的上游弃用警告。
- 已运行 `git diff --check`，未发现空白或行尾问题。
- 文章元数据接入后已运行 `uv run ruff check .`，通过。
- 文章元数据接入后已运行 `uv run pytest tests\test_content_service.py tests\test_admin_content_api.py tests\test_public_content_api.py`，18 个测试通过；仍存在 FastAPI TestClient 上游弃用警告。
- 文章元数据接入后已运行后端全量 `uv run pytest`，88 个测试通过、2 个 Redis 集成测试因未配置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI TestClient 与 Starlette TestClient cookies 的上游弃用警告。
- 已运行 `uv run alembic upgrade head --sql`，迁移升级 SQL 可生成并包含 `posts.seo_keywords`。
- 已运行 `uv run alembic downgrade 20260617_0005:20260616_0004 --sql`，迁移回滚 SQL 可生成。
- 已运行 `npm.cmd run lint`，通过。
- 已运行 `npm.cmd run build`，通过；仍存在 KaTeX 主 chunk 超过 500KB 的既有提示。
- 已在真实运行库执行 `uv run alembic upgrade head`，从 `20260616_0004` 升级到 `20260617_0005`。
- 已启动本地后端 `uv run python main.py` 并运行增强后的 `uv run python scripts/verify_runtime_publish_flow.py`，验证分类、标签、SEO 信息、未来定时文章不提前公开、公开文章详情和文件访问链路均通过。
- 真实运行库文章元数据验证结束后已关闭本次启动的后端服务，并确认 `18080`、`15173`、`14173` 均无监听。
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
- 已使用本机真实 MySQL 临时库 `blog_codex_cleanup_verify` 运行 Alembic 迁移和服务层文件清理闭环，确认软删除清理扫描 1 条、删除记录 1 条、删除物理文件 1 个；孤儿 dry-run 扫描 2 个、孤儿 1 个、删除 0 个；孤儿显式删除扫描 2 个、孤儿 1 个、删除 1 个。
- 已使用本机真实 MySQL 临时库 `blog_codex_cleanup_cli_verify` 运行 Alembic 迁移和 CLI 文件清理闭环，确认 `cleanup-deleted-files`、`cleanup-orphan-files` dry-run、`cleanup-orphan-files --delete` 均按预期输出和修改临时上传目录。
- 已确认 CLI 验证结束后 `blog_codex_cleanup_cli_verify` 临时库不存在，`backend/var/codex-cleanup-cli-verify` 临时上传目录不存在。
- Redis 限流适配器接入后已运行 `uv run ruff check .`，通过。
- Redis 限流适配器接入后已运行 `uv run pytest tests\test_rate_limit.py tests\test_admin_security.py tests\test_admin_encryption_api.py`，15 个测试通过；仍存在 FastAPI TestClient 上游弃用警告。
- Redis 限流适配器接入后已重新运行后端全量 `uv run pytest`，87 个测试通过；仍存在 FastAPI TestClient 与 per-request cookies 的上游弃用警告。
- Redis 限流适配器接入后已运行 `docker compose -f deploy\docker-compose.yml -f deploy\docker-compose.prod.yml config --quiet`，配置可展开。
- Redis 限流适配器接入后已运行 `git diff --check`，未发现空白或行尾问题。
- 维护任务 systemd 示例接入后已运行文本结构检查，确认 3 个 service 与 3 个 timer 均包含必要 section、调度时间、`WorkingDirectory=/opt/blog` 和预期 CLI 命令，且孤儿文件扫描 service 未包含 `--delete`。
- 维护任务 systemd 示例接入后已重新运行 `docker compose -f deploy\docker-compose.yml -f deploy\docker-compose.prod.yml config --quiet`，配置可展开。
- 维护任务 systemd 示例接入后已重新运行 `git diff --check`，未发现空白或行尾问题。
- 本机 Windows 环境没有 `systemd-analyze`，未能执行 systemd 原生 `verify`；已用文本结构检查覆盖示例文件关键字段，生产 Debian 上安装前仍建议运行 `systemd-analyze verify deploy/systemd/*.service deploy/systemd/*.timer`。
- 真实 Redis 集成测试接入后已运行 `uv run ruff check .`，通过。
- 未设置 `BLOG_TEST_REDIS_URL` 时已运行 `uv run pytest tests\test_rate_limit_redis_integration.py`，2 个测试按预期跳过；仍存在 FastAPI TestClient 上游弃用警告。
- 已下载一次性 Windows Redis `v5.0.14.1` zip 到临时目录并启动在 `127.0.0.1:16379`，设置 `BLOG_TEST_REDIS_URL=redis://127.0.0.1:16379/15` 后运行 `uv run pytest tests\test_rate_limit_redis_integration.py`，2 个测试通过；仍存在 FastAPI TestClient 上游弃用警告。
- 真实 Redis 集成测试结束后已确认没有 `redis-server` 遗留进程，临时目录 `%TEMP%\codex-blog-redis-verify` 不存在。
- 已重新运行后端全量 `uv run pytest`，87 个测试通过、2 个真实 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI TestClient 与 per-request cookies 的上游弃用警告。
- 真实 Redis 集成测试文档同步后已重新运行 `uv run ruff check .`，通过。
- 真实 Redis 集成测试文档同步后已重新运行 `uv run pytest tests\test_rate_limit.py tests\test_rate_limit_redis_integration.py`，5 个测试通过、2 个真实 Redis 集成测试因未设置 `BLOG_TEST_REDIS_URL` 跳过；仍存在 FastAPI TestClient 上游弃用警告。
- 真实 Redis 集成测试文档同步后已重新运行 `docker compose -f deploy\docker-compose.yml -f deploy\docker-compose.prod.yml config --quiet`，配置可展开。
- 真实 Redis 集成测试文档同步后已重新运行 `git diff --check`，未发现空白或行尾问题。

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

## 2026-06-18

### 已完成

- 优化后台管理公共布局：文章、页面、文件、友链和设置等页面的后台面板从紧挤三栏调整为列表侧栏 + 主编辑区 + 辅助预览区的响应式布局。
- 优化后台交互反馈：扩大列表行、分组行、标签页、输入框和按钮的命中区域，补充 hover、active 和键盘焦点状态。
- 修复前台与后台数据更新后界面不主动刷新的问题：增加查询缓存失效工具，后台写操作会同步失效对应的后台列表和公开页面缓存。
- 调整 React Query 默认刷新策略：保留 8 秒 `staleTime` 作为快速点击限流，窗口聚焦、网络恢复和过期后重新进入页面会自动拉取。
- 修复公开页面浏览器标题没有跟随站点设置的问题：页面 SEO 统一从公开站点资料读取站点名，全局标题组件只作为无页面 SEO 时的兜底。

### 进行中

- 后台管理体验继续细化，当前重点是布局可读性、状态刷新和标题一致性。

### 阻塞与风险

- 真实后台页面视觉截图需要可用的本地后端和数据库；本次主要通过前端构建、lint 与样式结构检查验证。
- 前端打包仍存在 Vite 大 chunk 提醒，暂不影响本次 UI 和刷新修复。

### 下一步

- 在真实后端数据环境下复查后台文章、文件、友链和设置页面的面板间距、保存后刷新和公开页面标题。

### 验证

- 已运行 `npm.cmd run build`，通过；Vite 仍提示主 chunk 大于 500 kB。
- 已运行 `npm.cmd run lint`，通过。
- 已关闭本次启动的前端开发服务，并确认 `15173` 无本项目开发服务监听。

## 2026-06-18

### 已完成

- 按 `https://innei.in/` 的公开页动效方向补充前台动画：顶部浮动导航入场、导航 active/hover 下划线、首页头像轻浮动、社交圆形按钮上浮、页面切入、滚动显现和时间线绘制。
- 强化公开列表交互：近期文章、文章归档、文件列表、站点入口、常用入口和碎念条目补充 hover 位移、标题强调、图标位移和封面缩放反馈。
- 补充 `prefers-reduced-motion` 兜底，用户系统关闭动效时不会强行动画。
- 保留公开导航半透明玻璃背景，让滚动时正文可轻微透出。
- 参考 `https://innei.in/` 的字体体系，将其实际下发的 `Instrument Sans` woff2 下载到本地资源，并接入 MiSans 中文分片 webfont，确保中文正文不再只依赖本机是否安装 MiSans。
- 修正公开页字体栈顺序，将 MiSans 提到系统 fallback 前面，避免 Windows 先走系统中文回退导致字体体感不变化。
- 为全站文本选区增加独立的自绘笔刷覆盖层：桌面端隐藏原生选区背景，按真实文字行绘制带斜切端点、纤维纹理和刷入动画的 accent 选区。
- 稳定选区笔刷拖动状态：选区行 key 不再绑定坐标和宽度，坐标取整并改用 `translate3d` 定位，避免拖选时反复重建 stroke 导致抖动。
- 调整选区笔刷适用边界：公开页和正文预览的可见文本默认可显示笔刷，隐藏文本、图标按钮和表单控件不生成笔刷覆盖。
- 按视觉复查反馈恢复公开页旧字体体系：移除新增的 Instrument Sans 与 MiSans webfont，公开页标题回到原有衬线字体气质。
- 收敛公开页大标题字号：首页主标题和文章归档页标题均下调 clamp 上限，避免标题在桌面首屏显得过重。
- 为文章正文和后台内容预览链接增加自定义标记样式，去掉默认下划线链接外观。

### 进行中

- 公开页视觉体验继续细化，下一步在真实内容环境下复查字体、正文链接和动效节奏。

### 阻塞与风险

- 本次本地视觉验证未启动后端，公开接口请求会报错并展示空态；动效、布局和导航遮挡已通过前端页面截图检查。
- 前端打包仍存在 Vite 大 chunk 提醒，暂不影响本次动效调整。

### 下一步

- 在真实后端数据环境下复查文章正文链接、选区样式、后台内容预览和 MiSans 字体加载体感。

### 验证

- 已运行 `npm.cmd run build`，通过；Vite 仍提示主 chunk 大于 500 kB。
- 已运行 `npm.cmd run lint`，通过。
- 已使用 Playwright CLI + Microsoft Edge 检查 `http://127.0.0.1:15173/` 桌面首屏、滚动状态和 390px 移动端截图，截图保存到已忽略的 `output/playwright`；控制台接口错误来自未启动后端。
- 已使用 Playwright CLI + Microsoft Edge 检查 `document.fonts`：`Instrument Sans` 可用，MiSans 中文分片已实际加载；文章正文链接为自定义标记样式且无默认下划线。
- 已使用 Playwright CLI + Microsoft Edge 选中首页标题并截图检查笔刷选区覆盖层，截图保存到已忽略的 `output/playwright/selection-brush.png`。
- 已使用 Playwright CLI + Microsoft Edge 模拟逐步扩大标题选区，确认同一行笔刷 stroke 在拖选过程中保持同一个 DOM 节点，截图保存到已忽略的 `output/playwright/selection-brush-stable.png`。
- 已使用 Playwright CLI + Microsoft Edge 检查标题、统计、列表标题可显示笔刷，社交图标按钮不生成笔刷矩形，截图保存到已忽略的 `output/playwright/selection-icon-buttons-skipped.png`。
- 已使用 Playwright CLI + Microsoft Edge 复查首页和文章归档页标题字号与字体，截图保存到已忽略的 `output/playwright/title-home-smaller.png` 与 `output/playwright/title-posts-smaller.png`。
