# 遥测上报数据设计

本文按照当前遥测摄入 API 设计本博客项目应该上报的数据。摄入端使用 Project API Key，通过 `X-API-Key: tlm_xxx` 或 `Authorization: Bearer tlm_xxx` 发送；不要把后台登录 token、Cookie、CSRF Token 或 `project_id` 放入遥测请求。

## 接入边界

- 第一阶段只允许服务端上报：`blog-backend`、后台维护任务和部署脚本可以持有 Project API Key；浏览器前端不能内置 Project API Key。
- 前端如需上报 Web Vitals 或 JS 错误，必须先走后端受控转发接口，后端负责脱敏、限流和补充项目 API Key。
- 业务主流程不能同步阻塞在遥测发送上；后端应本地内存队列或后台任务异步发送，失败只影响观测数据。
- 所有上报都使用 UTF-8 JSON，单批不超过 100 条和 256 KB；高频事件优先聚合成指标。
- 当前实现通过后端环境变量控制是否上传：`BLOG_TELEMETRY_ENABLED=false` 默认关闭，启用时还必须提供 `BLOG_TELEMETRY_ENDPOINT` 和 `BLOG_TELEMETRY_API_KEY`。Project API Key 只放在 `backend/.env` 或 `deploy/env/backend.env`，不进入前端配置、浏览器包或请求参数。

## 通用标签

建议所有 metrics/logs/spans 使用这些低基数字段：

| 字段 | 位置 | 示例 | 说明 |
| --- | --- | --- | --- |
| `source` | 顶层 | `blog-backend` | 来源服务；trace 拓扑也依赖它 |
| `environment` | tags/payload | `production` | 来自 `settings.environment` |
| `version` | tags/payload | `1.0.0` | 来自 `settings.version` |
| `component` | tags | `public-api` / `admin-api` / `encryption` / `files` / `tasks` | 模块边界 |
| `scope` | tags | `public` / `admin` / `system` | API 或任务范围 |
| `route` | tags | `/api/public/posts/{slug}` | 必须使用路由模板，不用真实 path |
| `method` | tags | `GET` | HTTP 方法 |
| `status_code` | tags | `200` | 字符串形式便于过滤 |
| `status_family` | tags | `2xx` / `4xx` / `5xx` | 汇总错误率 |
| `entity_type` | tags/payload | `post` / `file` / `friend_link` | 业务实体类型 |
| `action` | tags/payload | `post.publish` | 后台审计动作或公开访问类型 |
| `outcome` | tags | `ok` / `error` / `limited` / `denied` / `deduped` | 统一结果 |

不要把这些内容上报到 tags 或 payload：密码、Project API Key、JWT、Refresh Token、Cookie、CSRF Token、`X-Encryption-Session`、`esid`、salt lease、密钥材料、nonce、密文、数据库连接串、完整 URL/query、签名 token、文章标题、slug、正文、外部 URL、文件名、MIME、完整设置值、原始 IP、完整 UA。

## 指标

指标用于趋势和告警，尽量低基数，实体 ID 放 payload，不放 tags。

| 指标名 | 类型 | 单位 | 上报时机 | tags | payload |
| --- | --- | --- | --- | --- | --- |
| `blog.http.server.request.count` | counter | count | 每个后端请求结束 | `method`、`route`、`scope`、`component`、`status_code`、`status_family`、`outcome` | 无 |
| `blog.http.server.duration` | histogram | ms | 每个后端请求结束 | 同上 | 无 |
| `blog.http.server.error.count` | counter | count | 4xx/5xx 或未捕获异常 | `route`、`status_code`、`error_type`、`component` | `request_id` |
| `blog.rate_limit.hit.count` | counter | count | `enforce_rate_limit()` 命中 | `event_type`、`scope`、`component`、`rate_limit_backend` | `retry_after_seconds` |
| `blog.encryption.session.created.count` | counter | count | `/api/{scope}/encryption/sessions` 创建成功 | `scope`、`profile` | `active_limit` |
| `blog.encryption.session.rejected.count` | counter | count | 加密会话公钥无效、活跃数超限或限流 | `scope`、`reason` | 无 |
| `blog.encryption.salt.websocket.closed.count` | counter | count | salt WSS 关闭 | `scope`、`close_code`、`reason_class` | 无 |
| `blog.encryption.salt.lease.count` | counter | count | salt lease 签发或消费 | `scope`、`purpose`、`profile`、`stage=issued/consumed/rejected` | 无 |
| `blog.auth.login.count` | counter | count | 登录成功、失败、限流 | `outcome`、`reason_class` | `actor_id` 仅成功时可选 |
| `blog.content.write.count` | counter | count | 文章、页面创建/更新/发布/删除 | `action`、`entity_type`、`status`、`visibility` | `entity_id`、`changed_fields_count` |
| `blog.public.post.view.count` | counter | count | 公开文章 view 接口处理后 | `outcome=recorded/deduped/error` | `entity_id` |
| `blog.public.post.like.count` | counter | count | 公开文章 like 接口处理后 | `outcome=changed/noop/risk_limited/error`、`liked=true/false` | `entity_id` |
| `blog.file.upload.count` | counter | count | 后台上传成功或失败 | `outcome`、`visibility`、`public_listed` | `entity_id` |
| `blog.file.upload.bytes` | histogram | bytes | 后台上传成功 | `visibility`、`public_listed` | 无 |
| `blog.file.access.count` | counter | count | 公开下载、文章图片渲染、缩略图、后台短时链接 | `access_type`、`status_code`、`outcome` | `entity_id` |
| `blog.friend_link.application.count` | counter | count | 公开友链申请 | `outcome=accepted/duplicate/global_limited/domain_limited/rate_limited/error` | `entity_id` |
| `blog.site_nav.visit.count` | counter | count | 公开小网站跳转计数 | `outcome=redirect/not_found/deduped` | `entity_id` |
| `blog.task.completed.count` | counter | count | CLI/定时维护任务结束 | `task_name`、`outcome` | `duration_ms` |
| `blog.task.deleted.rows` | gauge | count | 日志/加密会话/文件清理任务结束 | `task_name`、`table` | 无 |
| `blog.friend_link.health.count` | gauge | count | 友链健康检查结束 | `outcome=healthy/unhealthy/skipped` | 无 |

`blog.public.post.view.count` 当前由服务层精确上报 `recorded/deduped`，`blog.public.post.like.count` 当前由点赞状态机精确上报 `changed/noop/risk_limited`。

示例：

```json
{
  "metrics": [
    {
      "name": "blog.http.server.duration",
      "value": 42.8,
      "unit": "ms",
      "type": "histogram",
      "source": "blog-backend",
      "tags": {
        "environment": "production",
        "version": "1.0.0",
        "component": "public-api",
        "scope": "public",
        "method": "GET",
        "route": "/api/public/posts/{slug}",
        "status_code": "200",
        "status_family": "2xx",
        "outcome": "ok"
      }
    }
  ]
}
```

## 事件

事件用于低频但重要的业务事实。后台审计日志和安全事件已经有清晰语义，遥测事件应直接复用这些动作名，不额外暴露正文或 URL。

| 事件类型 | 上报来源 | payload |
| --- | --- | --- |
| `blog.admin.audit` | `record_admin_audit()` | `action`、`entity_type`、`entity_id`、`actor_id`、`changed_fields`、`status`、`visibility`、`public_listed`、`show_in_nav`、`review_status`、`deleted`、`is_public` |
| `blog.content.lifecycle` | 文章/页面创建、更新、发布、删除 | `action`、`entity_type`、`entity_id`、`actor_id`、`status`、`visibility`、`changed_fields` |
| `blog.file.uploaded` | 后台文件上传成功 | `entity_id`、`visibility`、`public_listed`、`size_bytes` |
| `blog.file.deleted` | 后台文件删除 | `entity_id`、`actor_id` |
| `blog.file.temporary_url.created` | 后台或公开短时链接创建 | `scope`、`entity_id`、`expires_seconds` |
| `blog.friend_link.application.created` | 公开友链申请成功 | `entity_id`、`status=pending` |
| `blog.friend_link.reviewed` | 后台友链审核 | `entity_id`、`actor_id`、`review_status` |
| `blog.site_nav.visit.recorded` | 小网站跳转首访计数 | `entity_id`、`status_code=302` |
| `blog.security.rate_limit.hit` | `enforce_rate_limit()` | `event_type`、`scope`、`profile`、`credential`、`action`、`retry_after_seconds` |
| `blog.security.encryption_session_active_limited` | 单 IP 活跃加密会话超限 | `scope`、`profile` |
| `blog.task.completed` | `cleanup-*`、`check-friend-links` | `task_name`、`outcome`、`deleted_count`、`healthy_count`、`unhealthy_count`、`duration_ms` |
| `blog.deployment.finished` | 部署脚本或 CI | `version`、`environment`、`git_sha`、`status`、`duration_seconds` |

示例：

```json
{
  "type": "blog.admin.audit",
  "source": "blog-backend",
  "payload": {
    "environment": "production",
    "version": "1.0.0",
    "action": "post.publish",
    "entity_type": "post",
    "entity_id": 123,
    "actor_id": 1,
    "status": "published",
    "visibility": "public",
    "published_at_set": true
  }
}
```

## 日志

日志只用于排障和安全分析，不替代访问日志表。不要把每个成功请求都作为 log 上报。

| level | message | 上报时机 | attributes | payload |
| --- | --- | --- | --- | --- |
| `error` | `Unhandled request error` | 未捕获异常或 5xx | `route`、`method`、`component`、`status_code`、`error_type`、`request_id` | 生产只放脱敏错误指纹；非生产可放截断 stack |
| `warn` | `Rate limit hit` | 限流命中 | `event_type`、`route`、`scope`、`component` | `retry_after_seconds` |
| `warn` | `Invalid encryption request` | 加密会话、esid、salt 或 login capsule 校验失败 | `scope`、`profile`、`route`、`reason_class` | 无 |
| `warn` | `File access denied` | 文件 token 无效、文章未引用、公开性不满足 | `access_type`、`route`、`status_code` | `entity_id` |
| `warn` | `Maintenance item skipped` | 文件清理发现不安全路径、友链检查目标不安全等 | `task_name`、`reason_class` | 只放计数，不放路径或 URL |
| `info` | `Maintenance task completed` | 定时任务完成 | `task_name`、`outcome` | 汇总计数 |

生产日志 payload 不应包含 SQL、请求体、响应体、密文、栈中可能带出的路径 query、外部 URL 或文件名。

## Trace Span

trace 用于定位慢请求和依赖瓶颈。建议采样规则：

- 100% 上报 5xx、429、后台写操作、维护任务。
- 100% 上报耗时超过 1000 ms 的请求。
- 公开 GET 成功请求按 5% 到 10% 采样。
- 不上报请求体、响应体、SQL 文本、真实 path/query、slug、文件名、URL 和密钥材料。

推荐 span：

| span name | source | parent | attributes |
| --- | --- | --- | --- |
| `HTTP GET /api/public/posts/{slug}` | `blog-backend` | root | `route`、`method`、`scope`、`status_code` |
| `validate public encryption session` | `blog-backend` | HTTP root | `scope=public`、`profile=content-v1` |
| `validate admin auth` | `blog-backend` | HTTP root | `scope=admin` |
| `rate_limit.check` | `blog-redis` / `blog-backend` | HTTP root | `rule`、`backend`、`outcome` |
| `db.query` | `blog-mysql` | HTTP root | `operation=select/insert/update/delete`、`model` |
| `render markdown preview` | `blog-backend` | HTTP root | `entity_type=post` |
| `file.upload.validate` | `blog-backend` | HTTP root | `size_bucket` |
| `file.storage.write` | `blog-storage` | HTTP root | `visibility` |
| `file.thumbnail.generate` | `blog-backend` | HTTP root | `outcome` |
| `avatar.cache.fetch` | `blog-backend` | HTTP root | `outcome`、`status_family` |
| `task cleanup-logs` | `blog-maintenance` | root | `task_name` |

同一个 HTTP 请求内生成 `trace_id`，根 span 是路由模板，内部 Redis/MySQL/Storage span 按父子关系关联。跨请求的文章图片、公开文件下载等不强行与文章详情请求关联，除非后续在短时签名中安全地携带不可逆 trace continuation。

## 当前挂载点

当前后端已按这些位置落地第一版：

- `app.main.create_app()`：HTTP middleware 统一记录 `blog.http.server.*` 指标，并按错误、慢请求、后台写操作和公开 GET 采样规则上报 root span。
- `app.api.admin.audit.record_admin_audit()`：上报 `blog.admin.audit` 事件和后台内容写入指标。
- `LogService.record_access_log()`：只在访问日志实际落库后上报公开文件访问和站点跳转指标；短时去重命中时不重复上报。
- `app.api.limits.enforce_rate_limit()`：上报限流指标、`blog.security.rate_limit.hit` 事件和 warn log。
- `app.api.admin.encryption`、`app.api.public.encryption`、`app.api.encryption_salts.salt_websocket()` 和 salt lease 服务：上报加密会话、salt WSS 关闭和 lease 签发/消费/拒绝指标。
- `PostInteractionService.record_view()`、`PostInteractionService.set_like()`：上报 `recorded/deduped/changed/noop/risk_limited` 互动指标。
- 后台/公开文件路由与文件管理路由：上报上传成功/失败、上传体积、删除事件和短时链接创建事件；文件下载/文章图片访问通过访问日志服务统一上报。
- 公开友链申请、后台友链审核和站点跳转路由：上报申请结果、审核事件、跳转首访和去重结果。
- `app.tasks.*`：维护任务结束时上报任务完成指标、事件、日志和 root span。
- `deploy/scripts/upgrade_backend_db.sh` 通过 `python -m app.cli record-deployment-finished` 在数据库升级脚本退出时尽力上报 `blog.deployment.finished`。

## 落地状态

1. 已新增 `TelemetryService` adapter，读取 `BLOG_TELEMETRY_ENDPOINT`、`BLOG_TELEMETRY_API_KEY`、`BLOG_TELEMETRY_ENABLED`，并实现异步队列、批量发送、429 `Retry-After`、5xx 短重试、100 条/256 KB 切块和超大单项丢弃。
2. 已接入 HTTP middleware、`enforce_rate_limit()`、`record_admin_audit()` 三个高价值低侵入点。
3. 已接入文件、公开文章互动、加密 salt WSS、友链/站点跳转和维护任务的业务指标与事件。
4. 已加入采样 trace，并只对错误、慢请求、后台写操作、维护任务和少量公开 GET 成功请求上报 root span。
5. 已为遥测失败使用本地 debug/warn 日志记录原因，不记录遥测 API Key。
