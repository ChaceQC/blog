import { ExternalLink } from 'lucide-react'

import { StatusBadge } from '../../components/StatusBadge.tsx'
import type { FriendLink } from './sampleLinks.ts'

const statusLabels = {
  healthy: '正常',
  pending: '待审核',
} satisfies Record<FriendLink['status'], string>

type FriendLinkListProps = {
  links: FriendLink[]
}

export function FriendLinkList({ links }: FriendLinkListProps) {
  return (
    <div className="compact-list">
      {links.map((link) => (
        <a className="compact-row" href={link.url} key={link.id}>
          <span>
            <strong>{link.name}</strong>
            <small>{link.description}</small>
          </span>
          <span className="compact-row__meta">
            <StatusBadge tone={link.status}>{statusLabels[link.status]}</StatusBadge>
            <ExternalLink size={16} strokeWidth={1.8} aria-hidden="true" />
          </span>
        </a>
      ))}
    </div>
  )
}
