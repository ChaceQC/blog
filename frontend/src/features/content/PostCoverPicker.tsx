import { useQuery } from '@tanstack/react-query'
import { Image } from 'lucide-react'

import { listAdminFiles } from '../files/api.ts'
import type { AdminFileItem } from '../files/types.ts'

type PostCoverPickerProps = {
  value: number | null
  onChange: (value: number | null) => void
  disabled?: boolean
}

export function PostCoverPicker({
  value,
  onChange,
  disabled = false,
}: PostCoverPickerProps) {
  const filesQuery = useQuery({
    queryKey: ['admin-files'],
    queryFn: listAdminFiles,
  })
  const imageFiles = (filesQuery.data?.items ?? []).filter(isCoverCandidate)
  const selectedFile = imageFiles.find((file) => file.id === value) ?? null

  return (
    <div className="cover-picker">
      <label>
        封面图片
        <select
          disabled={disabled || filesQuery.isLoading}
          value={value ?? ''}
          onChange={(event) => {
            const nextValue = event.target.value
            onChange(nextValue === '' ? null : Number(nextValue))
          }}
        >
          <option value="">不设置封面</option>
          {imageFiles.map((file) => (
            <option key={file.id} value={file.id}>
              {file.original_name}
            </option>
          ))}
        </select>
      </label>
      <div className="cover-picker__list">
        {imageFiles.map((file) => (
          <button
            className={
              file.id === value
                ? 'cover-picker__item active'
                : 'cover-picker__item'
            }
            disabled={disabled}
            key={file.id}
            onClick={() => onChange(file.id === value ? null : file.id)}
            type="button"
          >
            <Image size={16} strokeWidth={1.8} aria-hidden="true" />
            <span>
              <strong>{file.original_name}</strong>
              <small>
                {file.width && file.height
                  ? `${file.width} × ${file.height}`
                  : file.mime_type}
              </small>
            </span>
          </button>
        ))}
      </div>
      {filesQuery.isError ? (
        <p className="form-error">封面列表暂时无法加载</p>
      ) : null}
      {!filesQuery.isLoading && imageFiles.length === 0 ? (
        <p className="empty-state">还没有可用于封面的公开图片。</p>
      ) : null}
      {selectedFile ? (
        <p className="cover-picker__hint">当前封面：{selectedFile.original_name}</p>
      ) : null}
    </div>
  )
}

function isCoverCandidate(file: AdminFileItem): boolean {
  return (
    file.status === 'active' &&
    file.visibility === 'public' &&
    file.mime_type.startsWith('image/')
  )
}
