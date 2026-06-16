import { API_BASE_URL } from '../../api/config.ts'
import type { PublicPostItem } from './types.ts'

export const DEFAULT_POST_COVER_URL = '/default-cover.svg'

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

export function formatPostDate(value: string | null): string {
  if (!value) {
    return '未标记日期'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '未标记日期'
  }

  return dateFormatter.format(date).replaceAll('/', '-')
}

export function getReadingMinutes(wordCount: number): number {
  return Math.max(1, Math.ceil(wordCount / 400))
}

export function formatRelativePostDate(value: string | null): string {
  if (!value) {
    return '刚刚'
  }

  const publishedAt = new Date(value).getTime()
  if (Number.isNaN(publishedAt)) {
    return '刚刚'
  }

  const days = Math.max(
    0,
    Math.floor((Date.now() - publishedAt) / (24 * 60 * 60 * 1000)),
  )

  return days === 0 ? '今天' : `${days} 天前`
}

export function publicApiAssetUrl(value: string): string {
  if (/^https?:\/\//.test(value)) {
    return value
  }

  const origin = API_BASE_URL.replace(/\/api$/, '')
  const path = value.startsWith('/') ? value : `/${value}`
  return `${origin}${path}`
}

export function postCoverUrl(post: Pick<PublicPostItem, 'cover_image_url'>): string {
  return post.cover_image_url
    ? publicApiAssetUrl(post.cover_image_url)
    : DEFAULT_POST_COVER_URL
}
