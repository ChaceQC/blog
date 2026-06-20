import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { FriendLinkList } from './FriendLinkList.tsx'
import type { FriendLink } from './types.ts'

const baseLink: FriendLink = {
  id: 1,
  group_name: '朋友们',
  name: '静海月兔大学',
  url: 'https://friend.example.test',
  avatar_url: null,
  description: '虚构的世界',
  sort_order: 0,
}

describe('FriendLinkList', () => {
  afterEach(() => {
    cleanup()
  })

  it('uses a default avatar when a friend link has no avatar url', () => {
    render(<FriendLinkList links={[baseLink]} />)

    const avatar = screen.getByRole('img', { name: '静海月兔大学 的头像' })

    expect(avatar.getAttribute('src')).toBe('/default-avatar.svg')
  })

  it('uses the configured avatar when it is present', () => {
    render(
      <FriendLinkList
        links={[
          {
            ...baseLink,
            avatar_url: 'https://cdn.example.test/avatar.png',
          },
        ]}
      />,
    )

    const avatar = screen.getByRole('img', { name: '静海月兔大学 的头像' })

    expect(avatar.getAttribute('src')).toBe('https://cdn.example.test/avatar.png')
  })
})
