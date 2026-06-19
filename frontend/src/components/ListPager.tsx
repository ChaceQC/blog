import { ChevronLeft, ChevronRight } from 'lucide-react'

type ListPagerProps = {
  page: number
  pageSize: number
  totalItems: number
  showWhenSinglePage?: boolean
  isLoading?: boolean
  variant?: 'public' | 'admin'
  onPageChange: (page: number) => void
}

export function ListPager({
  page,
  pageSize,
  totalItems,
  showWhenSinglePage = false,
  isLoading = false,
  variant = 'public',
  onPageChange,
}: ListPagerProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const hasPreviousPage = page > 0
  const hasNextPage = page < totalPages - 1

  if (!showWhenSinglePage && totalItems <= pageSize && page === 0) {
    return null
  }

  return (
    <div className={variant === 'admin' ? 'pagination-bar pagination-bar--compact' : 'pagination-bar'}>
      <button
        className="text-button text-button--muted"
        disabled={!hasPreviousPage || isLoading}
        onClick={() => onPageChange(Math.max(0, page - 1))}
        type="button"
      >
        <ChevronLeft size={16} strokeWidth={1.8} aria-hidden="true" />
        上一页
      </button>
      <span>
        第 {page + 1} / {totalPages} 页
      </span>
      <button
        className="text-button text-button--muted"
        disabled={!hasNextPage || isLoading}
        onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
        type="button"
      >
        下一页
        <ChevronRight size={16} strokeWidth={1.8} aria-hidden="true" />
      </button>
    </div>
  )
}
