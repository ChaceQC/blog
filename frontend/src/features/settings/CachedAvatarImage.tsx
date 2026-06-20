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
  const cachedSrc = useCachedAvatarUrl(src)

  return (
    <img
      {...imageProps}
      alt={alt}
      onError={fallbackToDefaultAvatar}
      src={cachedSrc}
    />
  )
}

function useCachedAvatarUrl(sourceUrl: string | null | undefined): string {
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
    void loadCachedAvatarUrl(avatarUrl)
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
          setCachedAvatar((current) =>
            current?.sourceUrl === avatarUrl ? null : current,
          )
        }
      })

    return () => {
      cancelled = true
      if (objectUrl) {
        revokeAvatarObjectUrl(objectUrl)
      }
    }
  }, [avatarUrl])

  return cachedAvatar?.sourceUrl === avatarUrl
    ? cachedAvatar.resolvedUrl
    : avatarUrl
}

async function loadCachedAvatarUrl(sourceUrl: string): Promise<string> {
  const cache = await caches.open(AVATAR_CACHE_NAME)
  const request = avatarCacheRequest(sourceUrl)
  const cached = await cache.match(request)
  if (cached && isFreshCachedAvatar(cached)) {
    return responseToObjectUrl(cached)
  }

  const response = await fetch(sourceUrl, {
    cache: 'force-cache',
    credentials: 'omit',
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
  return (
    typeof caches !== 'undefined' &&
    typeof URL.createObjectURL === 'function' &&
    sourceUrl !== DEFAULT_AVATAR_URL &&
    !sourceUrl.startsWith('blob:') &&
    !sourceUrl.startsWith('data:')
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
