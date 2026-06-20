import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CachedAvatarImage } from './CachedAvatarImage.tsx'

type CacheEntry = {
  request: Request
  response: Response
}

describe('CachedAvatarImage', () => {
  let entries: CacheEntry[]
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>
  let objectUrlIndex: number

  beforeEach(() => {
    entries = []
    objectUrlIndex = 0
    fetchMock = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('caches', createCachesStub(entries))
    vi.spyOn(URL, 'createObjectURL').mockImplementation(
      () => `blob:avatar-${++objectUrlIndex}`,
    )
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('uses a fresh frontend cached avatar before fetching', async () => {
    entries.push({
      request: avatarRequest('/api/public/avatar-cache/token'),
      response: new Response(new Blob(['cached'], { type: 'image/png' }), {
        headers: {
          'Content-Type': 'image/png',
          'X-Blog-Avatar-Cached-At': String(Date.now()),
        },
      }),
    })

    render(
      <CachedAvatarImage
        alt="头像"
        src="/api/public/avatar-cache/token"
      />,
    )

    await waitFor(() => {
      expect(screen.getByRole('img', { name: '头像' }).getAttribute('src')).toBe(
        'blob:avatar-1',
      )
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetches and stores an avatar when the frontend cache misses', async () => {
    fetchMock.mockResolvedValue(
      new Response(new Blob(['fresh'], { type: 'image/png' }), {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      }),
    )

    render(
      <CachedAvatarImage
        alt="头像"
        src="/api/public/avatar-cache/token"
      />,
    )

    await waitFor(() => {
      expect(screen.getByRole('img', { name: '头像' }).getAttribute('src')).toBe(
        'blob:avatar-1',
      )
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/public/avatar-cache/token', {
      cache: 'force-cache',
      credentials: 'omit',
    })
    expect(entries).toHaveLength(1)
    expect(entries[0].response.headers.get('X-Blog-Avatar-Cached-At')).not.toBeNull()
  })
})

function createCachesStub(entries: CacheEntry[]): CacheStorage {
  return {
    open: vi.fn(async () => createCacheStub(entries)),
  } as unknown as CacheStorage
}

function createCacheStub(entries: CacheEntry[]): Cache {
  return {
    match: vi.fn(async (request: RequestInfo | URL) => {
      const key = requestKey(request)
      return entries.find((entry) => requestKey(entry.request) === key)?.response
    }),
    put: vi.fn(async (request: RequestInfo | URL, response: Response) => {
      entries.push({ request: avatarRequest(request), response })
    }),
  } as unknown as Cache
}

function requestKey(request: RequestInfo | URL): string {
  return avatarRequest(request).url
}

function avatarRequest(request: RequestInfo | URL): Request {
  if (request instanceof Request) {
    return request
  }
  return new Request(new URL(String(request), window.location.origin))
}
