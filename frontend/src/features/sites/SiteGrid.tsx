import { ArrowUpRight } from 'lucide-react'

import type { SiteItem } from './sampleSites.ts'

type SiteGridProps = {
  sites: SiteItem[]
}

export function SiteGrid({ sites }: SiteGridProps) {
  return (
    <div className="site-grid">
      {sites.map((site) => (
        <a className="site-tile" href={site.url} key={site.id}>
          <span>
            <strong>{site.title}</strong>
            <small>{site.group}</small>
          </span>
          <p>{site.description}</p>
          <ArrowUpRight size={18} strokeWidth={1.8} aria-hidden="true" />
        </a>
      ))}
    </div>
  )
}
