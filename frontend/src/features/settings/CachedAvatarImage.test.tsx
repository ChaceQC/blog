import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CachedAvatarImage } from './CachedAvatarImage.tsx'

type CacheEntry = {
  request: Request
  response: Response
}

describe('CachedAvatarImage', () => {
  let entries: CacheEntry[]
  let deletedKeys: string[]
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

  beforeEach(() => {
    entries = []
    deletedKeys = []
    fetchMock = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('caches', createCachesStub(entries, deletedKeys))
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('uses a fresh frontend cached avatar before fetching', async () => {
    entries.push({
      request: avatarRequest('/api/public/avatar-cache/token'),
      response: avatarResponse('cached', {
        headers: {
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
        'data:image/png;base64,Y2FjaGVk',
      )
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetches and stores an avatar when the frontend cache misses', async () => {
    fetchMock.mockResolvedValue(
      avatarResponse('fresh', {
        status: 200,
      }),
    )

    render(
      <CachedAvatarImage
        alt="头像"
        src="/api/public/avatar-cache/token"
      />,
    )

    expect(screen.getByRole('img', { name: '头像' }).getAttribute('src')).toBe(
      '/default-avatar.svg',
    )

    await waitFor(() => {
      expect(screen.getByRole('img', { name: '头像' }).getAttribute('src')).toBe(
        'data:image/png;base64,ZnJlc2g=',
      )
    })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/public/avatar-cache/token',
      expect.objectContaining({
        cache: 'no-cache',
        credentials: 'same-origin',
        signal: expect.any(AbortSignal),
      }),
    )
    expect(entries).toHaveLength(1)
    expect(entries[0].response.headers.get('X-Blog-Avatar-Cached-At')).not.toBeNull()
  })

  it('does not use Cache Storage for external avatar urls', () => {
    render(
      <CachedAvatarImage
        alt="头像"
        src="https://cdn.example.test/avatar.png"
      />,
    )

    expect(screen.getByRole('img', { name: '头像' }).getAttribute('src')).toBe(
      'https://cdn.example.test/avatar.png',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('deletes a broken frontend cached avatar when the cached image fails to load', async () => {
    entries.push({
      request: avatarRequest('/api/public/avatar-cache/token'),
      response: avatarResponse('broken', {
        headers: {
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
        'data:image/png;base64,YnJva2Vu',
      )
    })

    screen.getByRole('img', { name: '头像' }).dispatchEvent(new Event('error'))

    await waitFor(() => {
      expect(deletedKeys).toContain(
        new URL('/api/public/avatar-cache/token', window.location.origin).href,
      )
    })
    expect(screen.getByRole('img', { name: '头像' }).getAttribute('src')).toBe(
      '/default-avatar.svg',
    )
  })
})

function createCachesStub(
  entries: CacheEntry[],
  deletedKeys: string[],
): CacheStorage {
  return {
    open: vi.fn(async () => createCacheStub(entries, deletedKeys)),
  } as unknown as CacheStorage
}

function createCacheStub(entries: CacheEntry[], deletedKeys: string[]): Cache {
  return {
    match: vi.fn(async (request: RequestInfo | URL) => {
      const key = requestKey(request)
      return entries.find((entry) => requestKey(entry.request) === key)?.response
    }),
    put: vi.fn(async (request: RequestInfo | URL, response: Response) => {
      entries.push({ request: avatarRequest(request), response })
    }),
    delete: vi.fn(async (request: RequestInfo | URL) => {
      deletedKeys.push(requestKey(request))
      return true
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

function avatarResponse(
  body: string,
  init: ResponseInit = {},
): Response {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'image/png')
  return new Response(body, { ...init, headers })
}
