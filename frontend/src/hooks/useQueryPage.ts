import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

export function useQueryPage(paramName = 'page') {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parseQueryPage(searchParams.get(paramName))
  const setPage = useCallback(
    (nextPage: number) => {
      setSearchParams((current) => queryPageParams(current, nextPage, paramName))
    },
    [paramName, setSearchParams],
  )

  return { page, searchParams, setPage }
}

export function parseQueryPage(value: string | null): number {
  const page = Number.parseInt(value ?? '1', 10)
  if (Number.isNaN(page) || page < 1) {
    return 0
  }
  return page - 1
}

function queryPageParams(
  current: URLSearchParams,
  nextPage: number,
  paramName: string,
): URLSearchParams {
  const next = new URLSearchParams(current)
  if (nextPage <= 0) {
    next.delete(paramName)
  } else {
    next.set(paramName, String(nextPage + 1))
  }
  return next
}
