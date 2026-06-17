import { ArrowUpRight } from 'lucide-react'

import { publicSiteItemVisitUrl } from './api.ts'
import { siteNavTagLabels } from './siteNavTags.ts'
import type { SiteItem } from './types.ts'

type SiteGridProps = {
  sites: SiteItem[]
}

export function SiteGrid({ sites }: SiteGridProps) {
  return (
    <div className="site-grid">
      {sites.map((site) => {
        const tags = siteNavTagLabels(site.tags_json)
        return (
          <a
            className="site-tile"
            href={publicSiteItemVisitUrl(site.id)}
            key={site.id}
            rel={site.open_target === 'blank' ? 'noreferrer' : undefined}
            target={site.open_target === 'blank' ? '_blank' : '_self'}
          >
            <div className="site-tile__head">
              {site.icon_url ? (
                <img
                  alt=""
                  className="site-tile__icon"
                  loading="lazy"
                  src={site.icon_url}
                />
              ) : null}
              <span>
                <strong>{site.title}</strong>
                <small>{site.group_name ?? site.group_slug ?? '入口'}</small>
              </span>
            </div>
            <p>{site.description ?? '常用站点入口'}</p>
            {tags.length > 0 ? (
              <div className="site-tile__tags">
                {tags.map((tag) => (
                  <span key={tag}>#{tag}</span>
                ))}
              </div>
            ) : null}
            <ArrowUpRight
              className="site-tile__arrow"
              size={17}
              strokeWidth={1.8}
              aria-hidden="true"
            />
          </a>
        )
      })}
    </div>
  )
}
