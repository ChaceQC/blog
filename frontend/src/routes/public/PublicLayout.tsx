import {
  BookOpen,
  Compass,
  FolderOpen,
  Home,
  Link as LinkIcon,
  Settings,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'

import {
  isRateLimitError,
  RATE_LIMIT_MESSAGE,
} from '../../api/client.ts'
import { getPublicSiteProfile } from '../../features/settings/api.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'

const RATE_LIMIT_NOTICE_VISIBLE_MS = 8_000

export function PublicLayout() {
  const queryClient = useQueryClient()
  const [rateLimitNoticeUntil, setRateLimitNoticeUntil] = useState(0)
  const { data: siteProfile, error: siteProfileError } = useQuery({
    queryKey: ['public-site-profile'],
    queryFn: ({ signal }) => getPublicSiteProfile({ signal }),
  })
  const title = siteProfile?.title ?? siteSettings.title
  const showRateLimitNotice =
    isRateLimitError(siteProfileError) || rateLimitNoticeUntil > 0

  useEffect(() => {
    const showRecentRateLimitNotice = () => {
      setRateLimitNoticeUntil(Date.now() + RATE_LIMIT_NOTICE_VISIBLE_MS)
    }
    const unsubscribeQueries = queryClient.getQueryCache().subscribe((event) => {
      if (
        event.type === 'updated' &&
        isPublicQueryKey(event.query.queryKey) &&
        isRateLimitError(event.query.state.error)
      ) {
        showRecentRateLimitNotice()
      }
    })
    const unsubscribeMutations = queryClient
      .getMutationCache()
      .subscribe((event) => {
        if (
          event.type === 'updated' &&
          isRateLimitError(event.mutation.state.error)
        ) {
          showRecentRateLimitNotice()
        }
      })

    return () => {
      unsubscribeQueries()
      unsubscribeMutations()
    }
  }, [queryClient])

  useEffect(() => {
    if (rateLimitNoticeUntil <= Date.now()) {
      return
    }
    const timeoutId = window.setTimeout(
      () => setRateLimitNoticeUntil(0),
      rateLimitNoticeUntil - Date.now(),
    )
    return () => window.clearTimeout(timeoutId)
  }, [rateLimitNoticeUntil])

  return (
    <div className="public-shell">
      <header className="site-header">
        <NavLink className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">
            <BookOpen size={18} strokeWidth={1.8} />
          </span>
          <span>{title}</span>
        </NavLink>
        <nav aria-label="前台导航">
          <NavLink to="/" end>
            <Home size={16} strokeWidth={1.8} aria-hidden="true" />
            首页
          </NavLink>
          <NavLink to="/posts">文章</NavLink>
          <NavLink to="/links">
            <LinkIcon size={16} strokeWidth={1.8} aria-hidden="true" />
            友链
          </NavLink>
          <NavLink to="/files">
            <FolderOpen size={16} strokeWidth={1.8} aria-hidden="true" />
            文件
          </NavLink>
          <NavLink to="/sites">
            <Compass size={16} strokeWidth={1.8} aria-hidden="true" />
            导航
          </NavLink>
          <NavLink to="/admin">
            <Settings size={16} strokeWidth={1.8} aria-hidden="true" />
            后台
          </NavLink>
        </nav>
      </header>
      {showRateLimitNotice ? (
        <p className="public-shell__notice" role="alert">
          {RATE_LIMIT_MESSAGE}
        </p>
      ) : null}
      <main>
        <Outlet />
      </main>
    </div>
  )
}

function isPublicQueryKey(queryKey: readonly unknown[]): boolean {
  const [scope] = queryKey
  return typeof scope === 'string' && scope.startsWith('public-')
}
