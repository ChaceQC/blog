import { useQuery } from '@tanstack/react-query'
import { FileImage, UploadCloud } from 'lucide-react'
import { Link } from 'react-router-dom'

import { listAdminFiles } from './api.ts'

export function FileQueuePreview() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['admin-files'],
    queryFn: listAdminFiles,
  })
  const files = data?.items ?? []

  return (
    <section className="admin-panel">
      <div className="section-heading">
        <span>
          <UploadCloud size={18} strokeWidth={1.8} aria-hidden="true" />
          最近素材
        </span>
        <Link className="icon-button" to="/admin/files" aria-label="上传文件">
          <UploadCloud size={18} strokeWidth={1.8} />
        </Link>
      </div>
      <div className="file-list">
        {files.slice(0, 5).map((file) => (
          <div className="file-row" key={file.id}>
            <FileImage size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>
              <strong>{file.original_name}</strong>
              <small>
                {file.mime_type} · {formatFileSize(file.size_bytes)}
              </small>
              <small>{file.object_key}</small>
            </span>
          </div>
        ))}
        {isError ? <p className="form-error">素材列表暂时打不开</p> : null}
        {!isLoading && !isError && files.length === 0 ? (
          <p className="empty-state">还没有文件。</p>
        ) : null}
      </div>
    </section>
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
