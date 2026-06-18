import { useMemo } from 'react'

export function usePagedItems<T>(
  items: readonly T[],
  page: number,
  pageSize: number,
): {
  safePage: number
  visibleItems: T[]
} {
  const safePage = safePageIndex(page, items.length, pageSize)
  const visibleItems = useMemo(
    () => items.slice(safePage * pageSize, safePage * pageSize + pageSize),
    [items, pageSize, safePage],
  )

  return { safePage, visibleItems }
}

export function safePageIndex(
  page: number,
  totalItems: number,
  pageSize: number,
): number {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  if (!Number.isFinite(page)) {
    return 0
  }
  return Math.min(Math.max(0, Math.trunc(page)), totalPages - 1)
}
