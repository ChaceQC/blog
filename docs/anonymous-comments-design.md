# 匿名评论功能设计

本文设计一个不要求公开访客登录的评论系统。核心思路不是把匿名用户伪装成账号，而是把能力拆开：展示用匿名身份，反垃圾用风险身份，删除用每条评论独立删除凭证，后台管理仍使用现有管理员登录和权限体系。

## 结论

- 公开访客不注册、不登录，也不需要邮箱。
- 评论展示使用可选昵称；未填写时显示 `匿名读者 #A1B2C3` 这类短身份。
- 删除权不依赖浏览器指纹。评论创建成功时服务端返回一枚只出现一次的 `delete_token`，前端保存在 localStorage 中，也可提供“复制删除凭证”能力。
- 服务端只保存 `delete_token_hash`，不保存原始删除凭证。
- 浏览器数据丢失后，访客无法自助证明自己是原作者，只能联系管理员处理。这是无登录系统的必要边界。
- 默认所有匿名评论进入待审核；如果以后想更实时，可以配置低风险自动发布。

## 设计目标

- 允许公开文章下展示评论、提交评论、回复评论和删除自己的评论。
- 在没有公开账号体系的前提下，给用户一个稳定但低隐私风险的匿名展示身份。
- 防止评论删除权被 URL、日志、数据库或遥测泄漏。
- 尽量复用当前项目已有能力：public scope 加密请求、匿名访客指纹、Redis/内存限流、后台审计日志、管理员权限和遥测脱敏策略。
- 默认适合公网部署，不把原始 IP、UA、浏览器高维指纹、评论删除 token、正文内容发到遥测。
- 把 XSS、CSRF/跨站提交、IDOR、删除 token 爆破、刷评论、日志注入、SQL 注入和 DoS 作为第一版必须覆盖的安全边界。

## 非目标

- 不做公开用户注册、登录、找回账号或跨设备同步。
- 不支持访客编辑已发评论。编辑比删除更容易产生身份和审计争议，后续可单独设计。
- 不把邮箱作为身份凭证。邮箱会引入隐私、验证和通知链路，第一版先不收集。
- 不做复杂嵌套楼中楼。第一版只支持一级评论和一级回复。

## 核心难点

匿名评论最难的是“谁有权删除”。浏览器指纹、IP、UA、语言、屏幕等都只能作为风险信号，不能作为所有权证明：

- 指纹会漂移，用户换浏览器、清缓存、换设备后会丢失。
- 指纹可能被伪造，不能作为删除凭据。
- IP 会变化，家庭网络、移动网络和代理都会让判断不稳定。
- 如果只靠昵称，任何人都可以冒充。

因此删除权必须来自一份明确的 bearer 凭证。它像一张“取件码”：谁持有对应评论的 `delete_token`，谁就能删除这条评论。丢失后无法恢复，但不会误删其他人内容。

## 匿名身份模型

### 三类身份

| 名称 | 用途 | 是否公开 | 是否可用于删除 |
| --- | --- | --- | --- |
| 展示身份 | 昵称、匿名短号、头像颜色 | 部分公开 | 否 |
| 风险身份 | 限流、反垃圾、重复检测 | 不公开 | 否 |
| 删除凭证 | 删除单条评论 | 不公开 | 是 |

### 前端本地状态

新增两个本地存储项：

| key | 内容 | 说明 |
| --- | --- | --- |
| `blog.public.comment.author_secret.v1` | 32 字节随机值的 hex/base64url 文本 | 生成匿名作者稳定身份，只用于当前浏览器 |
| `blog.public.comment.receipts.v1` | `{ comment_id, post_slug, delete_token, created_at }[]` | 保存每条评论的删除凭证 |

`author_secret` 可同时写入 localStorage 和 SameSite=Lax Cookie，方式可参考现有 `visitorFingerprint.ts`。Cookie 只用于同源恢复，不设 HttpOnly，因为前端需要读取后参与加密请求。

### 服务端派生字段

评论提交时，前端在 public scope 加密体中提交：

```json
{
  "author_secret_proof": "sha256(author_secret)",
  "fingerprint": { "...": "沿用现有 VisitorFingerprint" },
  "display_name": "可选昵称",
  "body_text": "评论正文"
}
```

服务端不要直接保存 `author_secret_proof`，而是用 `BLOG_SECRET_KEY` 做 HMAC 派生：

| 字段 | 生成方式 | 用途 |
| --- | --- | --- |
| `author_key_hash` | `HMAC(secret, "comment:author:" + author_secret_proof)` | 后台关联同一匿名作者、同浏览器找回自己的待审核评论 |
| `author_public_id` | `HMAC(secret, "comment:public:" + post_id + ":" + author_key_hash)` 截断 6 到 8 位 | 同一文章下稳定展示短号，不跨文章关联 |
| `risk_hash` | `HMAC(secret, ip_prefix + ua_short + language + fingerprint_risk_hash)` | 限流、反垃圾、重复提交检测 |
| `delete_token_hash` | `HMAC(secret, "comment:delete:" + delete_token)` | 删除凭证校验 |

展示身份按文章隔离，避免访客在不同文章下被公开串联。后台仍可以通过 `author_key_hash` 做必要风控，但后台列表默认只展示短摘要，不展示原始指纹。

## 展示规则

### 昵称

- 用户可填写 `display_name`，长度 1 到 32。
- 去掉首尾空白，折叠连续空白。
- 不允许控制字符。
- 不允许伪装管理员的保留名称，例如 `admin`、`管理员`、`站长`、`Chace` 等，保留词放配置中维护。
- 未填写时显示 `匿名读者 #A1B2C3`。

### 头像

第一版不接收头像 URL，不接收邮箱，不调用 Gravatar。

前端根据 `author_public_id` 生成本地 identicon、颜色圆点或首字母图案。这样不产生 SSRF、外部请求、跨站跟踪和头像版权问题。

### 评论内容

第一版使用纯文本，不使用 Markdown：

- 服务端保存 `body_text`。
- 前端和后台审核页都只能用普通文本节点渲染，推荐 React 默认文本转义加 CSS `white-space: pre-wrap`。
- 禁止把评论正文、昵称、删除占位文案传给 `dangerouslySetInnerHTML`、`innerHTML`、`insertAdjacentHTML` 或任何 HTML 模板拼接。
- 不允许 HTML。
- 不允许图片、iframe、视频、script。
- 链接第一版不自动变成 `<a>`；后续若需要自动链接，必须加 `rel="nofollow ugc noopener noreferrer"` 并继续限制协议。

默认限制：

| 项 | 建议值 |
| --- | --- |
| 正文长度 | 1 到 2000 字符 |
| 最大行数 | 30 |
| 单行长度 | 300 |
| 单条链接数量 | 0 或 2，取决于是否开启自动链接 |
| 回复深度 | 最多 2 层 |

## 安全威胁模型

评论功能是公开写入口，必须按不可信输入处理。第一版实现前，需要把下面防护点作为验收标准。

### XSS 与 HTML 注入

风险：

- 访客提交 `<script>`、事件属性、SVG、MathML、`javascript:` URL 或闭合标签，试图在公开文章页或后台审核页执行脚本。
- 管理员审核页更敏感，一旦后台被存储型 XSS 命中，攻击者可能借管理员会话执行后台操作。

约束：

- 评论正文和昵称默认纯文本，服务端不生成评论 HTML。
- 前端公开页和后台审核页都必须依赖 React 文本转义，不允许使用 `dangerouslySetInnerHTML` 展示评论字段。
- 换行只通过 CSS `white-space: pre-wrap` 处理，不把换行手写拼接成 HTML 字符串。
- 服务端校验并拒绝控制字符；保留普通换行和制表时，也要在日志与后台列表中做安全显示。
- 如果未来支持 Markdown，必须单独设计：禁用 raw HTML，复用后端 `MarkdownRenderer` 的 bleach allowlist，图片和链接协议继续白名单，且新增 XSS 回归测试后才能开启。

### DOM XSS 与前端状态污染

风险：

- localStorage 中的 receipt、昵称草稿或接口返回值被篡改后进入 DOM。
- 评论 id、cursor、状态等被拼接到选择器、URL 或 HTML 片段中。

约束：

- 从 localStorage 读取的 receipt 必须做 schema 校验：`comment_id` 为正整数，`post_slug` 符合 slug 规则，`delete_token` 长度和字符集符合约束。
- 前端只把 receipt 用于加密请求体，不直接展示 `delete_token`。
- cursor、comment id、post slug 只能通过 URL builder / `URLSearchParams` 拼接，不手写字符串插入 HTML。
- 前端不要把服务端返回的 `status`、`display_name` 当作 className 原样拼接；需要映射到固定枚举。

### CSRF、跨站提交与重放

风险：

- 第三方站点诱导浏览器向评论接口发起提交或删除请求。
- 攻击者重放旧的加密请求体重复提交评论或重复删除。

约束：

- 公开写接口必须使用现有 public scope `content-v1` 加密请求体，并要求有效加密会话、`esid` Cookie 和一次性 `X-Encryption-Esid-Salt`。
- 删除 token 只能放在加密请求体中，不能放 URL、query、fragment、Referer 或日志字段。
- `delete_token` 验证通过后的删除操作应幂等；重复删除返回相同删除状态或 404，但不能恢复正文。
- 评论创建接口应结合 `body_hash`、`risk_hash` 和短窗口去重，避免同一加密体被重放造成多条相同评论。

### IDOR 与越权删除

风险：

- 攻击者枚举 `comment_id`，尝试删除其他文章或其他人的评论。
- 回复接口把 `parent_id` 指向另一篇文章的评论，破坏数据边界。

约束：

- 所有评论读取、删除、审核都必须同时校验 `post_id` 和 `comment_id` 关系。
- `parent_id` 必须存在、属于同一篇文章、且不是已删除/拒绝/垃圾评论；第一版只允许回复顶层评论。
- 作者删除必须同时满足：评论属于当前文章、状态可删除、`delete_token_hash` 常量时间比较通过。
- 后台审核接口必须走管理员权限和 CSRF，不允许公开接口传状态直接发布。

### 删除 Token 安全

风险：

- token 过短被爆破。
- token 进入 URL、日志、遥测、报错、浏览器 Referer 或截图。
- 数据库泄漏后攻击者直接拿明文 token 删除评论。

约束：

- `delete_token` 使用至少 32 字节 CSPRNG 随机数，base64url 编码。
- 服务端只保存 `HMAC(secret, "comment:delete:" + delete_token)`，不保存明文。
- token 输入设置长度上限，例如 256 字符；超长值在进入 HMAC 前拒绝。
- 比较使用 `hmac.compare_digest`。
- 创建响应只返回一次明文 token；后台接口和日志永不返回。
- Nginx access log、应用访问日志、审计日志和遥测都不能包含 token。

### 评论刷量、垃圾内容与 DoS

风险：

- 高频提交压垮数据库或审核队列。
- 大请求体、超长正文、超多换行、复杂 Unicode 或重复内容增加处理成本。
- 攻击者批量制造待审核评论，占满磁盘或后台页面。

约束：

- 公开创建、owned 查询、作者删除都要限流；生产必须使用 Redis。
- 请求体大小、正文长度、昵称长度、receipt 数量、分页 limit、cursor 长度都必须有硬上限。
- 全站待审核评论数达到阈值时，公开提交返回 429 或 503，并给出普通提示。
- 正文规范化后生成 `body_hash`，同文章短窗口内重复正文直接拒绝或返回已有状态。
- 后台列表必须分页，不允许一次加载全部评论。

### SQL 注入、查询滥用与事务一致性

风险：

- sort/cursor/status/filter 直接拼接 SQL。
- 审核通过、删除和 `comment_count` 更新出现竞态，导致计数错误。

约束：

- Repository 使用 SQLAlchemy 表达式，不拼接原生 SQL。
- `status`、排序方向、筛选条件必须用固定枚举映射。
- 审核通过、作者删除、管理员删除和 `posts.comment_count` 更新放在同一事务。
- 对同一评论状态迁移使用行锁或带状态条件的 update，避免重复通过/重复扣减。

### 日志注入与后台展示

风险：

- 评论正文包含换行、控制字符或伪造日志片段，污染日志。
- 后台审核页把正文放进表格 title、tooltip、data 属性或 HTML attribute，触发注入。

约束：

- 评论正文、昵称不进入访问日志、审计日志、结构化应用日志和遥测。
- 后台审核页表格只展示截断纯文本摘要，详情区仍按文本节点渲染。
- 如果需要导出评论，导出文件必须转义 CSV/Excel 公式前缀，例如 `=`, `+`, `-`, `@`。

### 隐私与关联风险

风险：

- 同一匿名读者在不同文章下被公开关联。
- 后台或遥测保存可逆身份材料。

约束：

- 公开 `author_public_id` 按文章隔离，不能直接暴露全站稳定作者 id。
- `author_secret_proof`、fingerprint 明细、原始 IP、完整 UA 不落库。
- 风险字段只保存 HMAC 摘要和低精度 IP prefix，且遵循日志保留策略。

### 第三方资源与 SSRF

风险：

- 如果评论支持头像 URL、图片 URL 或自动展开链接，服务端可能被诱导请求内网地址，前端可能加载跟踪资源。

约束：

- 第一版不接收头像 URL，不支持评论图片，不做链接预览，不服务端抓取评论中的 URL。
- 如果未来允许外部资源，必须先复用头像缓存的 SSRF 校验策略，并新增协议、DNS、重定向、大小、MIME 和像素限制。

## 数据模型

新增 `post_comments` 表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | BIGINT PK | 评论 id |
| `post_id` | BIGINT FK | 所属文章 |
| `parent_id` | BIGINT nullable FK | 回复的评论 id，只允许指向同文章顶层评论 |
| `status` | VARCHAR(32) | `pending`、`published`、`rejected`、`deleted_by_author`、`deleted_by_admin`、`spam` |
| `display_name` | VARCHAR(64) nullable | 用户填写的昵称 |
| `author_public_id` | VARCHAR(32) | 展示短号和头像种子 |
| `author_key_hash` | CHAR(64) | 匿名作者内部哈希 |
| `fingerprint_hash` | CHAR(64) | 低风险身份摘要 |
| `risk_hash` | CHAR(64) | 反垃圾风险桶 |
| `delete_token_hash` | CHAR(64) nullable | 删除凭证哈希，删除后可置空 |
| `body_text` | TEXT | 评论正文，删除后清空 |
| `body_hash` | CHAR(64) | 正文规范化后 HMAC，用于重复检测 |
| `reply_count` | INT | 直接回复数 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |
| `reviewed_at` | DATETIME nullable | 审核时间 |
| `reviewed_by` | BIGINT nullable | 管理员 id |
| `deleted_at` | DATETIME nullable | 删除时间 |
| `deleted_reason` | VARCHAR(255) nullable | 删除原因分类，不放正文 |

给 `posts` 增加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `comment_count` | INT | 已发布评论数，不含待审核和删除 |

实现取舍：项目已有 `posts.allow_comment`，本轮直接复用该字段作为单篇文章评论开关，不再新增语义重复的 `comments_enabled`。

建议索引：

- `(post_id, status, created_at, id)`：公开列表。
- `(post_id, parent_id, status, created_at, id)`：回复列表。
- `(author_key_hash, created_at)`：后台风控和作者本地找回。
- `(risk_hash, created_at)`：限流和重复检测。
- `(post_id, body_hash, created_at)`：同文章重复内容检测。

## 状态机

| 当前状态 | 动作 | 新状态 | 说明 |
| --- | --- | --- | --- |
| 无 | 访客提交 | `pending` | 默认进入审核 |
| 无 | 访客提交且低风险自动发布开启 | `published` | 可配置，默认关闭 |
| `pending` | 管理员通过 | `published` | 增加 `posts.comment_count` |
| `pending` | 管理员拒绝 | `rejected` | 不公开 |
| `pending` | 作者凭证删除 | `deleted_by_author` | 清空正文 |
| `published` | 作者凭证删除 | `deleted_by_author` | 减少 `posts.comment_count`，有回复时保留占位 |
| `published` | 管理员删除 | `deleted_by_admin` | 减少 `posts.comment_count` |
| `pending` / `published` | 系统判垃圾 | `spam` | 不公开 |

删除后：

- `body_text` 清空。
- `delete_token_hash` 置空。
- `display_name` 可置空，公开只返回删除占位。
- 如果没有子回复，公开列表可直接不返回该评论。
- 如果有子回复，公开列表返回 tombstone：`评论已删除`。

## API 设计

所有公开写接口都使用现有 public scope `content-v1` 加密请求体，不把删除 token 放 URL。

### 公开列表

`GET /api/public/posts/{slug}/comments?limit=50&cursor=...`

返回 `published` 评论和必要 tombstone。响应继续使用 `EncryptedApiResponse`。

```json
{
  "items": [
    {
      "id": 123,
      "parent_id": null,
      "status": "published",
      "display_name": "匿名读者 #A1B2C3",
      "author_public_id": "A1B2C3",
      "body_text": "写得很好。",
      "reply_count": 0,
      "created_at": "2026-06-29T12:00:00"
    }
  ],
  "next_cursor": null,
  "total": 1
}
```

### 提交评论

`POST /api/public/posts/{slug}/comments`

加密请求体：

```json
{
  "parent_id": null,
  "display_name": "可选昵称",
  "body_text": "评论正文",
  "author_secret_proof": "sha256(author_secret)",
  "fingerprint": { "version": "web-v1" }
}
```

响应：

```json
{
  "comment": {
    "id": 123,
    "status": "pending",
    "display_name": "匿名读者 #A1B2C3",
    "author_public_id": "A1B2C3",
    "body_text": "评论正文",
    "created_at": "2026-06-29T12:00:00"
  },
  "delete_token": "一次性返回的随机删除凭证",
  "message": "评论已提交，等待审核"
}
```

前端收到后立刻把 `{ comment_id, post_slug, delete_token }` 写入 `blog.public.comment.receipts.v1`。服务端不再返回这枚 token。

### 查询自己的待审核评论

公开列表不应该暴露待审核评论。为了让原浏览器刷新后仍能看到“我提交过但待审核”的内容，新增：

`POST /api/public/posts/{slug}/comments/owned`

加密请求体：

```json
{
  "receipts": [
    { "comment_id": 123, "delete_token": "..." }
  ]
}
```

服务端最多接受 50 条 receipt，只返回 token 校验通过且属于当前文章的评论。这样不依赖指纹，也不会让别人枚举待审核内容。

### 作者删除

`POST /api/public/posts/{slug}/comments/{comment_id}/delete`

加密请求体：

```json
{
  "delete_token": "创建评论时返回的删除凭证"
}
```

成功后返回：

```json
{
  "id": 123,
  "status": "deleted_by_author"
}
```

删除失败统一返回 `404` 或 `403`，不要区分 token 错、文章错、评论错过细，避免枚举。

### 后台管理

沿用 `/api/admin`、管理员 Cookie、CSRF、`sensitive-v1` 或 `content-v1` 加密响应。

建议接口：

- `GET /api/admin/comments?status=pending&limit=50&offset=0`
- `PATCH /api/admin/comments/{comment_id}/review`：通过、拒绝、标记垃圾。
- `DELETE /api/admin/comments/{comment_id}`：管理员删除。
- `GET /api/admin/posts/{post_id}/comments`：按文章查看。

后台列表可以展示：

- 评论 id、文章 id/标题摘要、状态、创建时间。
- 昵称、匿名短号。
- 风险摘要，例如 `risk_hash` 前 8 位、同风险桶近 24 小时提交数。
- 正文内容仅在管理员审核界面展示，不进入审计日志和遥测。

## 反垃圾与限流

第一版建议默认保守：

- 所有评论默认 `pending`。
- 公开提交接口按 IP、`risk_hash`、`author_key_hash` 多维限流。
- 同一文章同一 `body_hash` 在短窗口内重复提交直接拒绝或返回已有待审核状态。
- 包含 URL、过短、过长、重复字符、过多换行、命中保留词时保持 `pending` 或标记 `spam_candidate`。
- 低风险自动发布作为配置项，默认关闭。

建议默认限流：

| 规则 | 默认值 |
| --- | --- |
| 同 IP 提交 | 5 条 / 10 分钟 |
| 同 `risk_hash` 提交 | 3 条 / 10 分钟 |
| 同 `author_key_hash` 提交 | 10 条 / 1 小时 |
| 同文章重复正文 | 1 条 / 10 分钟 |
| 全站待审核上限 | 500 条，超过后暂停公开提交 |

生产必须使用 Redis 后端，内存限流只用于本地开发和测试。

## 日志、遥测与隐私

应用访问日志：

- 记录 `public_comment_create`、`public_comment_delete`、`public_comments_list` 等 access_type。
- 不记录评论正文、昵称、删除 token、原始 IP、完整 UA、fingerprint、author_secret_proof。
- `detail_json` 只允许低基数字段，例如 `status=pending`、`outcome=rate_limited`。

后台审计日志：

- 记录 `comment.approve`、`comment.reject`、`comment.delete`。
- 只记录 `entity_id`、`post_id`、`status`、`reason_class`、`changed_fields`。
- 不记录评论正文和昵称。

遥测：

- `blog.comment.create.count`：tags 包含 `outcome`、`status`。
- `blog.comment.review.count`：tags 包含 `action=approve/reject/delete/spam`。
- `blog.comment.delete.count`：tags 包含 `scope=public/admin`、`outcome`。
- payload 只放 `entity_id`、`post_id`，不放正文、昵称、token、URL、slug。

## 前端交互

文章详情页下方新增评论区：

- 顶部显示已发布评论数。
- 评论列表按时间正序或倒序可配置，第一版建议正序，回复跟随父评论。
- 评论表单包含昵称和正文。昵称本地记忆。
- 提交后如果返回 `pending`，在当前浏览器里显示“待审核”状态。
- 本地有删除 receipt 的评论显示删除按钮。
- 删除时弹出确认，成功后立刻把本地 receipt 移除。
- 如果 localStorage 不可用，提交后提醒用户复制删除凭证；否则后续无法自助删除。

前端合并数据时：

1. 加载公开评论列表。
2. 从 localStorage 读取当前文章 receipts。
3. 调用 `comments/owned` 找回自己的待审核或已发布评论。
4. 合并并用 `comment_id` 去重。
5. 对本地持有 token 的评论显示删除按钮。

## 后端分层建议

保持当前项目分层：

- `models/comment.py`：`PostComment`。
- `schemas/comments.py`：公开和后台 DTO。
- `repositories/comments.py`：评论查询、状态迁移、计数更新。
- `services/comments.py`：评论创建、审核、删除、身份派生、反垃圾策略。
- `api/public/comments.py`：公开列表、提交、owned、删除。
- `api/admin/comments.py`：后台审核和删除。
- `services/comment_identity.py`：匿名身份和删除 token HMAC。
- `services/comment_moderation.py`：状态机、风控和内容规则。

不要把身份派生、限流、状态机直接塞进路由函数。

## 迁移与实现步骤

1. 新增数据模型和 Alembic 迁移：`post_comments`、`posts.comment_count`，并复用既有 `posts.allow_comment` 控制是否允许评论。
2. 新增 schema、repository、service，先完成纯服务层测试。
3. 接入公开 API：列表、创建、owned、作者删除。
4. 接入后台 API：待审核列表、通过、拒绝、删除。
5. 前端文章详情页增加评论区、本地 receipt 管理和删除交互。
6. 接入访问日志、审计日志和遥测，确认脱敏。
7. 增加维护任务：定期清理长期 `rejected/spam/deleted` 评论，或按保留策略清空正文。

## 测试清单

后端：

- 未发布、隐藏、私有、归档文章不能提交评论。
- `allow_comment=false` 时不能提交。
- 评论长度、昵称保留词、控制字符、回复深度校验。
- 创建评论只返回一次 `delete_token`，数据库不保存明文。
- 正确 token 可删除，错误 token 不能删除。
- 删除已发布评论会减少 `comment_count`。
- 有回复的删除评论返回 tombstone，无回复的删除评论不公开返回。
- 待审核评论不会出现在公开列表，但可通过 owned receipt 找回。
- 限流命中返回 429，并写安全事件或访问日志摘要。
- 审计日志和遥测不包含正文、昵称、token、fingerprint。

前端：

- localStorage 可用时自动保存 receipt。
- localStorage 不可用时提示复制删除凭证。
- 只有持有 receipt 的评论显示删除按钮。
- 刷新后能通过 owned 接口恢复自己的待审核评论。
- 删除后 receipt 被移除，界面显示删除状态。

安全回归：

- 评论正文中的 HTML 不执行。
- 删除 token 不出现在 URL、Nginx access log、应用访问日志和遥测中。
- 重复提交、爆破 token、超长 token、超长正文都被拒绝。

## 需要接受的产品边界

没有公开登录系统时，不能同时做到“完全匿名、跨设备可恢复、删除权强证明”。本设计选择：

- 匿名优先：不收邮箱、不建账号。
- 删除凭证优先：谁持有单条评论 token，谁能删除。
- 丢失不可恢复：本地数据丢失后只能找管理员。
- 审核优先：默认待审核，降低垃圾评论和公开风险。

这是个人博客场景下比较稳的折中。后续如果评论量明显增加，再考虑引入邮件一次性验证、OAuth 登录或第三方评论系统。
