import {
  Copy,
  FileArchive,
  FileImage,
  LockKeyhole,
  Search,
  UploadCloud,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { sampleFiles } from '../../features/files/sampleFiles.ts'

import type { ManagedFile } from '../../features/files/sampleFiles.ts'

const visibilityLabels = {
  public: '公开',
  private: '私有',
} satisfies Record<ManagedFile['visibility'], string>

export function AdminFilesPage() {
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState(sampleFiles[0]?.id ?? 0)
  const files = useMemo(
    () =>
      sampleFiles.filter((file) => {
        const keyword = query.trim().toLowerCase()
        if (!keyword) {
          return true
        }
        return (
          file.displayName.toLowerCase().includes(keyword) ||
          file.objectKey.toLowerCase().includes(keyword) ||
          file.mimeType.toLowerCase().includes(keyword)
        )
      }),
    [query],
  )
  const selectedFile =
    sampleFiles.find((file) => file.id === selectedId) ?? sampleFiles[0] ?? null

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>FILES</span>
        <h1>文件管理</h1>
        <button className="text-button admin-heading__action" disabled type="button">
          <UploadCloud size={17} strokeWidth={1.8} aria-hidden="true" />
          上传文件
        </button>
      </section>

      <div className="admin-workspace">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>文件列表</span>
            <small>共 {files.length} 件</small>
          </div>
          <label className="admin-search">
            <Search size={16} strokeWidth={1.8} aria-hidden="true" />
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索文件名、MIME 或 key"
              value={query}
            />
          </label>
          <div className="content-list">
            {files.map((file) => (
              <button
                className={file.id === selectedId ? 'content-row active' : 'content-row'}
                key={file.id}
                onClick={() => setSelectedId(file.id)}
                type="button"
              >
                <span>
                  <strong>{file.displayName}</strong>
                  <small>{file.objectKey}</small>
                </span>
                <small>{visibilityLabels[file.visibility]}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>文件详情</span>
            <small>本地存储</small>
          </div>
          {selectedFile ? (
            <div className="admin-detail">
              <div className="file-inspector">
                {selectedFile.mimeType.startsWith('image/') ? (
                  <FileImage size={22} strokeWidth={1.7} aria-hidden="true" />
                ) : (
                  <FileArchive size={22} strokeWidth={1.7} aria-hidden="true" />
                )}
                <span>
                  <strong>{selectedFile.displayName}</strong>
                  <small>
                    {selectedFile.mimeType} · {selectedFile.size}
                  </small>
                </span>
              </div>
              <dl className="detail-list">
                <div>
                  <dt>对象 key</dt>
                  <dd>{selectedFile.objectKey}</dd>
                </div>
                <div>
                  <dt>可见性</dt>
                  <dd>{visibilityLabels[selectedFile.visibility]}</dd>
                </div>
                <div>
                  <dt>引用</dt>
                  <dd>{selectedFile.usage}</dd>
                </div>
                <div>
                  <dt>更新时间</dt>
                  <dd>{selectedFile.updatedAt}</dd>
                </div>
              </dl>
              <div className="form-actions">
                <button className="text-button" disabled type="button">
                  <Copy size={17} strokeWidth={1.8} aria-hidden="true" />
                  复制链接
                </button>
                <button className="text-button text-button--muted" disabled type="button">
                  删除
                </button>
              </div>
            </div>
          ) : (
            <p className="empty-state">没有匹配的文件。</p>
          )}
        </section>

        <section className="admin-panel admin-panel--preview">
          <div className="section-heading">
            <span>上传策略</span>
            <small>
              <LockKeyhole size={14} strokeWidth={1.8} aria-hidden="true" />
              安全边界
            </small>
          </div>
          <div className="admin-note-list">
            <p>公开文件只读访问，私有文件走后端鉴权下载。</p>
            <p>真实存储路径使用英文 key，中文文件名只作为展示字段。</p>
            <p>后续接入上传 API 时校验 MIME、扩展名和文件头。</p>
          </div>
        </section>
      </div>
    </div>
  )
}
