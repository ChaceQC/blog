import { ExternalLink } from 'lucide-react'

import { DEFAULT_AVATAR_URL } from '../settings/avatar.ts'
import { CachedAvatarImage } from '../settings/CachedAvatarImage.tsx'
import type { FriendLink } from './types.ts'

type FriendLinkListProps = {
  links: FriendLink[]
}

export function FriendLinkList({ links }: FriendLinkListProps) {
  return (
    <div className="compact-list">
      {links.map((link) => (
        <a
          className="compact-row friend-link-row"
          href={link.url}
          key={link.id}
          rel="noreferrer"
          target="_blank"
        >
          <CachedAvatarImage
            alt={`${link.name} 的头像`}
            className="friend-link-row__avatar"
            loading="lazy"
            src={link.avatar_url ?? DEFAULT_AVATAR_URL}
          />
          <span className="friend-link-row__body">
            <strong>{link.name}</strong>
            <small>{link.description ?? link.group_name ?? '常去看看'}</small>
          </span>
          <span className="compact-row__meta">
            <small>{link.group_name ?? '友链'}</small>
            <ExternalLink size={16} strokeWidth={1.8} aria-hidden="true" />
          </span>
        </a>
      ))}
    </div>
  )
}
