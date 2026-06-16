import {
  Copy,
  Download,
  ExternalLink,
  FileArchive,
  FileImage,
  ImagePlus,
  Trash2,
} from 'lucide-react'

import { adminFileDownloadUrl } from './api.ts'

import type { AdminFileItem, AdminFileTemporaryUrlResponse } from './types.ts'

type FileDetailProps = {
  articleSlug: string
  file: AdminFileItem
  getTemporaryUrl: (file: AdminFileItem) => Promise<string | null>
  isDeleting: boolean
  isLinkLoading: boolean
  onArticleSlugChange: (slug: string) => void
  onDelete: () => void
  setNotice: (notice: string | null) => void
  temporaryUrl: AdminFileTemporaryUrlResponse | null
}

export function FileDetail({
  articleSlug,
  file,
  getTemporaryUrl,
  isDeleting,
  isLinkLoading,
  onArticleSlugChange,
  onDelete,
  setNotice,
  temporaryUrl,
}: FileDetailProps) {
  const isPublic = file.visibility === 'public'
  const isArticleImage = isPublic && file.mime_type.startsWith('image/')

  return (
    <div className="admin-detail">
      <div className="file-inspector">
        {file.mime_type.startsWith('image/') ? (
          <FileImage size={22} strokeWidth={1.7} aria-hidden="true" />
        ) : (
          <FileArchive size={22} strokeWidth={1.7} aria-hidden="true" />
        )}
        <span>
          <strong>{file.original_name}</strong>
          <small>
            {file.mime_type} · {formatFileSize(file.size_bytes)}
          </small>
        </span>
      </div>
      <dl className="detail-list">
        <div>
          <dt>文件 ID</dt>
          <dd>{file.id}</dd>
        </div>
        <div>
          <dt>存储路径</dt>
          <dd>{file.object_key}</dd>
        </div>
        <div>
          <dt>{isPublic ? '访问链接' : '访问范围'}</dt>
          <dd>
            {isPublic && temporaryUrl ? (
              <a href={temporaryUrl.url} target="_blank" rel="noreferrer">
                {temporaryUrl.url}
              </a>
            ) : isPublic ? (
              '按需生成，短时间内有效'
            ) : (
              '仅后台可见'
            )}
          </dd>
        </div>
        <div>
          <dt>公开文件栏</dt>
          <dd>{file.public_listed ? '展示' : '不展示'}</dd>
        </div>
        <div>
          <dt>尺寸</dt>
          <dd>{file.width && file.height ? `${file.width} × ${file.height}` : '未记录'}</dd>
        </div>
        <div>
          <dt>引用数</dt>
          <dd>{file.usage_count}</dd>
        </div>
        <div>
          <dt>更新时间</dt>
          <dd>{formatDate(file.updated_at)}</dd>
        </div>
        {temporaryUrl ? (
          <div>
            <dt>链接有效期</dt>
            <dd>{formatDate(temporaryUrl.expires_at)}</dd>
          </div>
        ) : null}
      </dl>
      {isArticleImage ? (
        <label className="inline-field">
          文章 Slug
          <input
            onChange={(event) => onArticleSlugChange(event.target.value)}
            placeholder="填写要引用这张图的文章 slug"
            value={articleSlug}
          />
        </label>
      ) : null}
      <div className="form-actions">
        <button
          className="text-button"
          onClick={() => void copyFileId(file, setNotice)}
          type="button"
        >
          <Copy size={17} strokeWidth={1.8} aria-hidden="true" />
          复制 ID
        </button>
        {isArticleImage ? (
          <button
            className="text-button"
            disabled={!articleSlug.trim()}
            onClick={() => void copyArticleImageLink(file, articleSlug, setNotice)}
            type="button"
          >
            <ImagePlus size={17} strokeWidth={1.8} aria-hidden="true" />
            复制文章引用
          </button>
        ) : null}
        <button
          className="text-button"
          disabled={!isPublic || isLinkLoading}
          onClick={() => void copyFileLink(file, getTemporaryUrl, setNotice)}
          type="button"
        >
          <Copy size={17} strokeWidth={1.8} aria-hidden="true" />
          {isLinkLoading ? '生成中' : '复制链接'}
        </button>
        {isPublic ? (
          <button
            className="text-button"
            disabled={isLinkLoading}
            onClick={() => void openFileLink(file, getTemporaryUrl, setNotice)}
            type="button"
          >
            <ExternalLink size={17} strokeWidth={1.8} aria-hidden="true" />
            打开
          </button>
        ) : null}
        <button
          className="text-button"
          onClick={() => openAdminDownload(file, setNotice)}
          type="button"
        >
          <Download size={17} strokeWidth={1.8} aria-hidden="true" />
          下载
        </button>
        <button
          className="text-button text-button--muted"
          disabled={isDeleting}
          onClick={onDelete}
          type="button"
        >
          <Trash2 size={17} strokeWidth={1.8} aria-hidden="true" />
          {isDeleting ? '删除中' : '删除'}
        </button>
      </div>
    </div>
  )
}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(value: string | null): string {
  if (!value) {
    return '未记录'
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function openAdminDownload(
  file: AdminFileItem,
  setNotice: (notice: string | null) => void,
) {
  const opened = window.open(
    adminFileDownloadUrl(file.id),
    '_blank',
    'noopener,noreferrer',
  )
  if (!opened) {
    setNotice('浏览器拦截了下载窗口，请允许弹出后重试')
  }
}

async function copyFileId(
  file: AdminFileItem,
  setNotice: (notice: string | null) => void,
) {
  navigator.clipboard
    .writeText(String(file.id))
    .then(() => setNotice('文件 ID 已复制'))
    .catch(() => setNotice('复制失败，请手动选择 ID'))
}

async function copyFileLink(
  file: AdminFileItem,
  getTemporaryUrl: (file: AdminFileItem) => Promise<string | null>,
  setNotice: (notice: string | null) => void,
) {
  let publicFileUrl: string | null
  try {
    publicFileUrl = await getTemporaryUrl(file)
  } catch {
    return
  }
  if (!publicFileUrl) {
    return
  }
  navigator.clipboard
    .writeText(publicFileUrl)
    .then(() => setNotice('链接已复制'))
    .catch(() => setNotice('复制失败，请手动选择链接'))
}

async function openFileLink(
  file: AdminFileItem,
  getTemporaryUrl: (file: AdminFileItem) => Promise<string | null>,
  setNotice: (notice: string | null) => void,
) {
  let publicFileUrl: string | null
  try {
    publicFileUrl = await getTemporaryUrl(file)
  } catch {
    return
  }
  if (!publicFileUrl) {
    return
  }

  const opened = window.open(publicFileUrl, '_blank', 'noopener,noreferrer')
  if (!opened) {
    setNotice('浏览器拦截了新窗口，请复制链接后打开')
  }
}

async function copyArticleImageLink(
  file: AdminFileItem,
  postSlug: string,
  setNotice: (notice: string | null) => void,
) {
  const slug = postSlug.trim()
  if (!slug) {
    setNotice('先填写文章 Slug')
    return
  }
  if (file.visibility !== 'public' || !file.mime_type.startsWith('image/')) {
    setNotice('只有公开图片能作为文章图片引用')
    return
  }

  const altText = file.alt_text?.trim() || file.original_name
  const markdown = `![${altText}](/api/public/posts/${slug}/files/${file.id}/render)`
  navigator.clipboard
    .writeText(markdown)
    .then(() => setNotice('文章引用已复制'))
    .catch(() => setNotice('复制失败，请手动选择引用'))
}
