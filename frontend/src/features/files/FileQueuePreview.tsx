import { FileImage, UploadCloud } from 'lucide-react'

const pendingFiles = [
  {
    id: 1,
    displayName: '封面书桌.jpg',
    objectKey: 'uploads/public/2026/06/cover-desk.jpg',
    type: 'image/jpeg',
    size: '420 KB',
  },
  {
    id: 2,
    displayName: '发布记录.pdf',
    objectKey: 'uploads/private/2026/06/launch-notes.pdf',
    type: 'application/pdf',
    size: '1.2 MB',
  },
]

export function FileQueuePreview() {
  return (
    <section className="admin-panel">
      <div className="section-heading">
        <span>
          <UploadCloud size={18} strokeWidth={1.8} aria-hidden="true" />
          文件队列
        </span>
        <button className="icon-button" type="button" aria-label="上传文件">
          <UploadCloud size={18} strokeWidth={1.8} />
        </button>
      </div>
      <div className="file-list">
        {pendingFiles.map((file) => (
          <div className="file-row" key={file.id}>
            <FileImage size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>
              <strong>{file.displayName}</strong>
              <small>
                {file.type} · {file.size}
              </small>
              <small>{file.objectKey}</small>
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
