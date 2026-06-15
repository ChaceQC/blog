import { apiGet } from '../../api/client.ts'

import type { PublicPostDetail, PublicPostListResponse } from './types.ts'

export function listPublicPosts(
  params: { limit?: number; offset?: number } = {},
): Promise<PublicPostListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 20))
  query.set('offset', String(params.offset ?? 0))

  return apiGet<PublicPostListResponse>(`/public/posts?${query.toString()}`)
}

export function getPublicPost(slug: string): Promise<PublicPostDetail> {
  return apiGet<PublicPostDetail>(`/public/posts/${encodeURIComponent(slug)}`)
}
