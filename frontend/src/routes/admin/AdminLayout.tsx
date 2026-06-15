import {
  FileText,
  FolderOpen,
  Link as LinkIcon,
  LogOut,
  Settings,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../../features/auth/useAuth.ts'

const adminLinks = [
  { to: '/admin', label: '总览', icon: FileText },
  { to: '/admin/files', label: '文件', icon: FolderOpen },
  { to: '/admin/links', label: '友链', icon: LinkIcon },
  { to: '/admin/settings', label: '设置', icon: Settings },
]

export function AdminLayout() {
  const { logout, session } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/admin/login', { replace: true })
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <NavLink className="brand brand--admin" to="/">
          个人博客 CMS
        </NavLink>
        <nav aria-label="后台导航">
          {adminLinks.map((item) => {
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
