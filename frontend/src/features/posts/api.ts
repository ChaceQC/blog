import { apiGetEncrypted } from '../../api/client.ts'

import type {
  PublicPostDetail,
  PublicPostListResponse,
  PublicTaxonomyListResponse,
} from './types.ts'

export function listPublicPosts(
  params: { limit?: number; offset?: number } = {},
): Promise<PublicPostListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 20))
  query.set('offset', String(params.offset ?? 0))

  return apiGetEncrypted<PublicPostListResponse>(
    `/public/posts?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}

export function getPublicPost(slug: string): Promise<PublicPostDetail> {
  return apiGetEncrypted<PublicPostDetail>(
    `/public/posts/${encodeURIComponent(slug)}`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}

export function listPublicCategories(
  params: { limit?: number; offset?: number } = {},
): Promise<PublicTaxonomyListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))

  return apiGetEncrypted<PublicTaxonomyListResponse>(
    `/public/categories?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}

export function listPublicTags(
  params: { limit?: number; offset?: number } = {},
): Promise<PublicTaxonomyListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))

  return apiGetEncrypted<PublicTaxonomyListResponse>(
    `/public/tags?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}
