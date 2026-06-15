import { FileImage, UploadCloud } from 'lucide-react'

import { sampleFiles } from './sampleFiles.ts'

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
        {sampleFiles.map((file) => (
          <div className="file-row" key={file.id}>
            <FileImage size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>
              <strong>{file.displayName}</strong>
              <small>
                {file.mimeType} · {file.size}
              </small>
              <small>{file.objectKey}</small>
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
