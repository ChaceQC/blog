import {
  BookOpen,
  Compass,
  FolderOpen,
  Home,
  Link as LinkIcon,
  Settings,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'

import { getPublicSiteProfile } from '../../features/settings/api.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'

export function PublicLayout() {
  const { data: siteProfile } = useQuery({
    queryKey: ['public-site-profile'],
    queryFn: getPublicSiteProfile,
  })
  const title = siteProfile?.title ?? siteSettings.title

  return (
    <div className="public-shell">
      <svg className="glass-filter-defs" aria-hidden="true" focusable="false">
        <filter
          id="nav-glass-refraction"
          x="-16%"
          y="-70%"
          width="132%"
          height="240%"
          colorInterpolationFilters="sRGB"
        >
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.018 0.052"
            numOctaves="2"
            seed="19"
            result="navNoise"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="navNoise"
            scale="16"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </svg>
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
      <main>
        <Outlet />
      </main>
    </div>
  )
}
