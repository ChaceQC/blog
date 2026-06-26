import { API_BASE_URL } from '../../api/config.ts'
import { formatChinaDate, parseApiTime } from '../../utils/datetime.ts'
import type { PublicPostItem } from './types.ts'

export const DEFAULT_POST_COVER_URL = '/default-cover.svg'

export function formatPostDate(value: string | null): string {
  return formatChinaDate(value, '未标记日期')
}

export function getReadingMinutes(wordCount: number): number {
  return Math.max(1, Math.ceil(wordCount / 400))
}

export function formatPostWordCount(wordCount: number): string {
  if (wordCount >= 10000) {
    return `${(wordCount / 10000).toFixed(1).replace(/\.0$/, '')} 万字`
  }
  return `${wordCount} 字`
}

export function formatRelativePostDate(value: string | null): string {
  if (!value) {
    return '刚刚'
  }

  const publishedAt = parseApiTime(value)
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
