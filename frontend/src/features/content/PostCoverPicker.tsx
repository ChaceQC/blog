import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { adminFileThumbnailUrl, listAdminFiles } from '../files/api.ts'
import type { AdminFileItem } from '../files/types.ts'

type PostCoverPickerProps = {
  value: number | null
  onChange: (value: number | null) => void
  disabled?: boolean
}

const coverPageSize = 8

export function PostCoverPicker({
  value,
  onChange,
  disabled = false,
}: PostCoverPickerProps) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const filesQuery = useQuery({
    queryKey: ['admin-files'],
    queryFn: listAdminFiles,
  })
  const imageFiles = useMemo(
    () =>
      (filesQuery.data?.items ?? [])
        .filter(isCoverCandidate)
        .filter((file) => {
          const keyword = query.trim().toLowerCase()
          return (
            keyword.length === 0 ||
            file.original_name.toLowerCase().includes(keyword) ||
            file.mime_type.toLowerCase().includes(keyword)
          )
        }),
    [filesQuery.data?.items, query],
  )
  const pageCount = Math.max(1, Math.ceil(imageFiles.length / coverPageSize))
  const visibleFiles = imageFiles.slice(
    page * coverPageSize,
    page * coverPageSize + coverPageSize,
  )
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
          {imageFiles.slice(0, 100).map((file) => (
            <option key={file.id} value={file.id}>
              {file.original_name}
            </option>
          ))}
        </select>
      </label>
      <label className="admin-search cover-picker__search">
        <Search size={16} strokeWidth={1.8} aria-hidden="true" />
        <input
          onChange={(event) => {
            setQuery(event.target.value)
            setPage(0)
          }}
          placeholder="搜索封面文件名"
          value={query}
        />
      </label>
      <div className="cover-picker__list">
        {visibleFiles.map((file) => (
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
            <img
              alt=""
              loading="eager"
              src={adminFileThumbnailUrl(file.id)}
              title={`${file.original_name} 缩略图`}
            />
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
      {imageFiles.length > coverPageSize ? (
        <div className="cover-picker__pager">
          <button
            className="icon-button"
            disabled={page === 0}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
            type="button"
            aria-label="上一页封面"
          >
            <ChevronLeft size={16} strokeWidth={1.8} aria-hidden="true" />
          </button>
          <span>
            {page + 1} / {pageCount}
          </span>
          <button
            className="icon-button"
            disabled={page >= pageCount - 1}
            onClick={() =>
              setPage((current) => Math.min(pageCount - 1, current + 1))
            }
            type="button"
            aria-label="下一页封面"
          >
            <ChevronRight size={16} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>
      ) : null}
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
