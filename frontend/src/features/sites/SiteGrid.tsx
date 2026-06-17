import { ArrowUpRight } from 'lucide-react'

import type { SiteItem } from './types.ts'

type SiteGridProps = {
  sites: SiteItem[]
}

export function SiteGrid({ sites }: SiteGridProps) {
  return (
    <div className="site-grid">
      {sites.map((site) => (
        <a
          className="site-tile"
          href={site.url}
          key={site.id}
          rel="noreferrer"
          target="_blank"
        >
          <span>
            <strong>{site.title}</strong>
            <small>{site.group_name ?? site.group_slug ?? '入口'}</small>
          </span>
          <p>{site.description ?? '常用站点入口'}</p>
          <ArrowUpRight size={17} strokeWidth={1.8} aria-hidden="true" />
        </a>
      ))}
    </div>
  )
}
