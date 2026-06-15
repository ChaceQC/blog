import { BookOpen, Compass, Home, Link as LinkIcon, Settings } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { siteSettings } from '../../features/settings/siteSettings.ts'

export function PublicLayout() {
  return (
    <div className="public-shell">
      <header className="site-header">
        <NavLink className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">
            <BookOpen size={18} strokeWidth={1.8} />
          </span>
          <span>{siteSettings.title}</span>
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
      <main>
        <Outlet />
      </main>
    </div>
  )
}
