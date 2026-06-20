import { useEffect, useState } from 'react'

import {
  DEFAULT_AVATAR_URL,
  fallbackToDefaultAvatar,
} from './avatar.ts'

import type { ImgHTMLAttributes } from 'react'

const AVATAR_CACHE_NAME = 'blog-avatar-cache-v1'
const AVATAR_CACHE_TTL_MS = 60 * 60 * 1000
const AVATAR_CACHED_AT_HEADER = 'X-Blog-Avatar-Cached-At'

type CachedAvatarImageProps = Omit<
  ImgHTMLAttributes<HTMLImageElement>,
  'alt' | 'onError' | 'src'
> & {
  alt: string
  src?: string | null
}

export function CachedAvatarImage({
  alt,
  src,
  ...imageProps
}: CachedAvatarImageProps) {
  const { discardCachedAvatar, resolvedUrl } = useCachedAvatarUrl(src)

  return (
    <img
      {...imageProps}
      alt={alt}
      onError={(event) => {
        discardCachedAvatar(event.currentTarget.src)
        fallbackToDefaultAvatar(event)
      }}
      src={resolvedUrl}
    />
  )
}

function useCachedAvatarUrl(sourceUrl: string | null | undefined): {
  discardCachedAvatar: (failedUrl: string) => void
  resolvedUrl: string
} {
  const avatarUrl = sourceUrl || DEFAULT_AVATAR_URL
  const [cachedAvatar, setCachedAvatar] = useState<{
    resolvedUrl: string
    sourceUrl: string
  } | null>(null)

  useEffect(() => {
    if (!shouldUseFrontendAvatarCache(avatarUrl)) {
      return
    }

    let cancelled = false
    let objectUrl: string | null = null
    const controller = new AbortController()

    void loadCachedAvatarUrl(avatarUrl, controller.signal)
      .then((loadedUrl) => {
        if (cancelled) {
          revokeAvatarObjectUrl(loadedUrl)
          return
        }
        objectUrl = loadedUrl
        setCachedAvatar({ sourceUrl: avatarUrl, resolvedUrl: loadedUrl })
      })
      .catch(() => {
        if (!cancelled) {
          setCachedAvatar({ sourceUrl: avatarUrl, resolvedUrl: DEFAULT_AVATAR_URL })
        }
      })

    return () => {
      cancelled = true
      controller.abort()
      if (objectUrl) {
        revokeAvatarObjectUrl(objectUrl)
      }
    }
  }, [avatarUrl])

  if (!shouldUseFrontendAvatarCache(avatarUrl)) {
    return {
      discardCachedAvatar: () => undefined,
      resolvedUrl: avatarUrl,
    }
  }

  return {
    discardCachedAvatar: (failedUrl: string) => {
      if (!failedUrl.startsWith('blob:')) {
        return
      }
      void discardCachedAvatar(avatarUrl)
      setCachedAvatar({ sourceUrl: avatarUrl, resolvedUrl: DEFAULT_AVATAR_URL })
    },
    resolvedUrl:
      cachedAvatar?.sourceUrl === avatarUrl
        ? cachedAvatar.resolvedUrl
        : DEFAULT_AVATAR_URL,
  }
}

async function loadCachedAvatarUrl(
  sourceUrl: string,
  signal: AbortSignal,
): Promise<string> {
  const cache = await caches.open(AVATAR_CACHE_NAME)
  const request = avatarCacheRequest(sourceUrl)
  const cached = await cache.match(request)
  if (cached && isFreshCachedAvatar(cached)) {
    return responseToObjectUrl(cached)
  }
  if (cached) {
    await cache.delete(request)
  }

  const response = await fetch(sourceUrl, {
    cache: 'no-cache',
    credentials: 'same-origin',
    signal,
  })
  if (!response.ok) {
    throw new Error('头像缓存请求失败')
  }
  const mediaType = response.headers.get('Content-Type') ?? ''
  if (!mediaType.startsWith('image/')) {
    throw new Error('头像响应不是图片')
  }
  const blob = await response.blob()
  const cachedResponse = new Response(blob, {
    headers: {
      'Content-Type': blob.type || mediaType,
      [AVATAR_CACHED_AT_HEADER]: String(Date.now()),
    },
  })
  await cache.put(request, cachedResponse.clone())
  return URL.createObjectURL(blob)
}

function avatarCacheRequest(sourceUrl: string): Request {
  return new Request(new URL(sourceUrl, window.location.origin), { method: 'GET' })
}

function shouldUseFrontendAvatarCache(sourceUrl: string): boolean {
  const url = frontendCacheUrl(sourceUrl)
  return (
    typeof caches !== 'undefined' &&
    typeof URL.createObjectURL === 'function' &&
    sourceUrl !== DEFAULT_AVATAR_URL &&
    !sourceUrl.startsWith('blob:') &&
    !sourceUrl.startsWith('data:') &&
    url !== null &&
    url.origin === window.location.origin &&
    url.pathname.startsWith('/api/public/avatar-cache/')
  )
}

function isFreshCachedAvatar(response: Response): boolean {
  const cachedAt = Number(response.headers.get(AVATAR_CACHED_AT_HEADER))
  return Number.isFinite(cachedAt) && Date.now() - cachedAt < AVATAR_CACHE_TTL_MS
}

async function responseToObjectUrl(response: Response): Promise<string> {
  return URL.createObjectURL(await response.blob())
}

function revokeAvatarObjectUrl(url: string): void {
  if (url.startsWith('blob:')) {
    URL.revokeObjectURL(url)
  }
}

async function discardCachedAvatar(sourceUrl: string): Promise<void> {
  try {
    const cache = await caches.open(AVATAR_CACHE_NAME)
    await cache.delete(avatarCacheRequest(sourceUrl))
  } catch {
    // Broken browser cache entries should not block avatar fallback rendering.
  }
}

function frontendCacheUrl(sourceUrl: string): URL | null {
  try {
    return new URL(sourceUrl, window.location.origin)
  } catch {
    return null
  }
}
