import {
  FileText,
  Files,
  FolderOpen,
  Link as LinkIcon,
  LogOut,
  Navigation,
  Newspaper,
  ScrollText,
  Settings,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { hasAnyAdminPermission } from '../../features/auth/permissions.ts'
import { useAuth } from '../../features/auth/useAuth.ts'
import { getPublicSiteProfile } from '../../features/settings/api.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'
import { adminAccess } from './adminAccess.ts'

const adminLinks = [
  { to: '/admin', label: '总览', icon: FileText, permissions: adminAccess.dashboard },
  { to: '/admin/posts', label: '文章', icon: Newspaper, permissions: adminAccess.posts },
  { to: '/admin/pages', label: '页面', icon: Files, permissions: adminAccess.pages },
  { to: '/admin/files', label: '文件', icon: FolderOpen, permissions: adminAccess.files },
  { to: '/admin/links', label: '友链', icon: LinkIcon, permissions: adminAccess.links },
  { to: '/admin/site-nav', label: '导航', icon: Navigation, permissions: adminAccess.siteNav },
  { to: '/admin/logs', label: '日志', icon: ScrollText, permissions: adminAccess.logs },
  { to: '/admin/settings', label: '设置', icon: Settings, permissions: adminAccess.settings },
]

export function AdminLayout() {
  const { logout, session } = useAuth()
  const navigate = useNavigate()
  const { data: siteProfile } = useQuery({
    queryKey: ['public-site-profile'],
    queryFn: getPublicSiteProfile,
  })
  const title = siteProfile?.title ?? siteSettings.title
  const visibleLinks =
    session === null
      ? []
      : adminLinks.filter((item) =>
          hasAnyAdminPermission(session.user, item.permissions),
        )

  useEffect(() => {
    document.title = title
  }, [title])

  async function handleLogout() {
    await logout()
    navigate('/admin/login', { replace: true })
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <NavLink className="brand brand--admin" to="/">
          {title}
        </NavLink>
        <nav aria-label="后台导航">
          {visibleLinks.map((item) => {
            const Icon = item.icon

            return (
              <NavLink end={item.to === '/admin'} to={item.to} key={item.label}>
                <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
                {item.label}
              </NavLink>
            )
          })}
        </nav>
        <div className="admin-session">
          <span>{session?.user.display_name ?? session?.user.username}</span>
          <button className="icon-button icon-button--dark" onClick={handleLogout}>
            <LogOut size={17} strokeWidth={1.8} aria-hidden="true" />
            <span className="sr-only">退出登录</span>
          </button>
        </div>
      </aside>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  )
}
