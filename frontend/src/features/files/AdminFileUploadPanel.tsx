import { FileUp, LockKeyhole } from 'lucide-react'

import type { ChangeEvent } from 'react'
import type { FileVisibility } from './types.ts'

type AdminFileUploadPanelProps = {
  uploadFile: File | null
  visibility: FileVisibility
  publicListed: boolean
  altText: string
  onUploadFileChange: (file: File | null) => void
  onVisibilityChange: (visibility: FileVisibility) => void
  onPublicListedChange: (publicListed: boolean) => void
  onAltTextChange: (altText: string) => void
}

export function AdminFileUploadPanel({
  uploadFile,
  visibility,
  publicListed,
  altText,
  onUploadFileChange,
  onVisibilityChange,
  onPublicListedChange,
  onAltTextChange,
}: AdminFileUploadPanelProps) {
  return (
    <section className="admin-panel admin-panel--editor">
      <div className="section-heading">
        <span>上传说明</span>
        <small>
          <LockKeyhole size={14} strokeWidth={1.8} aria-hidden="true" />
          文件夹
        </small>
      </div>
      <form className="content-form">
        <label>
          文件
          <span className="file-picker">
            <input
              accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
              className="file-picker__input"
              onChange={(event) => handleFileChange(event, onUploadFileChange)}
              type="file"
            />
            <span className="file-picker__action" aria-hidden="true">
              <FileUp size={17} strokeWidth={1.8} />
              {uploadFile ? '重新选择' : '选择文件'}
            </span>
            <span className="file-picker__summary">
              <strong>{uploadFile?.name ?? '尚未选择文件'}</strong>
              <small>
                {uploadFile
                  ? `${formatFileSize(uploadFile.size)} · ${
                      uploadFile.type || '未知类型'
                    }`
                  : 'JPEG、PNG、GIF、WebP 或 PDF，最大 20MB'}
              </small>
            </span>
          </span>
        </label>
        <div className="form-grid form-grid--two">
          <label>
            可见性
            <select
              onChange={(event) =>
                onVisibilityChange(event.target.value as FileVisibility)
              }
              value={visibility}
            >
              <option value="public">公开</option>
              <option value="private">私有</option>
            </select>
          </label>
          <label className="checkbox-field">
            <input
              checked={publicListed}
              disabled={visibility !== 'public'}
              onChange={(event) => onPublicListedChange(event.target.checked)}
              type="checkbox"
            />
            展示在公开文件栏
          </label>
          <label>
            替代文本
            <input
              onChange={(event) => onAltTextChange(event.target.value)}
              placeholder="用于图片说明"
              value={altText}
            />
          </label>
        </div>
      </form>
      <div className="admin-note-list">
        <p>可以上传 JPEG、PNG、GIF、WebP 和 PDF，单个文件不超过 20MB。</p>
        <p>文章图片使用渲染接口，公开文件栏下载才生成短时链接。</p>
        <p>删除后会先从列表移走，后面再统一清理原文件。</p>
      </div>
    </section>
  )
}

function handleFileChange(
  event: ChangeEvent<HTMLInputElement>,
  setUploadFile: (file: File | null) => void,
) {
  setUploadFile(event.target.files?.[0] ?? null)
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
