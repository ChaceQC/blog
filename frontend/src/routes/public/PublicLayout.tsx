import { BookOpen, Compass, Link as LinkIcon, Settings } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { siteSettings } from '../../features/settings/siteSettings.ts'

export function PublicLayout() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <NavLink className="brand" to="/">
          <BookOpen size={21} strokeWidth={1.8} aria-hidden="true" />
          <span>{siteSettings.title}</span>
        </NavLink>
        <nav aria-label="前台导航">
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
