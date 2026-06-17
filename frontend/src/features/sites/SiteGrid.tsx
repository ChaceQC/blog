import { ArrowUpRight } from 'lucide-react'

import { publicSiteItemVisitUrl } from './api.ts'
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
          href={publicSiteItemVisitUrl(site.id)}
          key={site.id}
          rel={site.open_target === 'blank' ? 'noreferrer' : undefined}
          target={site.open_target === 'blank' ? '_blank' : '_self'}
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
