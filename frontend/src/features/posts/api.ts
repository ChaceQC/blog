import { apiGetEncrypted, apiPostEncrypted } from '../../api/client.ts'

import type {
  PublicPageDetail,
  PublicPostInteractionPayload,
  PublicPostInteractionState,
  PublicPostDetail,
  PublicPostListResponse,
  PublicPostLikePayload,
  PublicTaxonomyItem,
  PublicTaxonomyListResponse,
} from './types.ts'

export function listPublicPosts(
  params: {
    limit?: number
    offset?: number
    categorySlug?: string
    tagSlug?: string
    signal?: AbortSignal
  } = {},
): Promise<PublicPostListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 20))
  query.set('offset', String(params.offset ?? 0))
  if (params.categorySlug) {
    query.set('category', params.categorySlug)
  }
  if (params.tagSlug) {
    query.set('tag', params.tagSlug)
  }

  return apiGetEncrypted<PublicPostListResponse>(
    `/public/posts?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public', signal: params.signal },
  )
}

export function getPublicPost(
  slug: string,
  options: { signal?: AbortSignal } = {},
): Promise<PublicPostDetail> {
  return apiGetEncrypted<PublicPostDetail>(
    `/public/posts/${encodeURIComponent(slug)}`,
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
  )
}

export function recordPublicPostView(
  slug: string,
  payload: PublicPostInteractionPayload,
  options: { signal?: AbortSignal } = {},
): Promise<PublicPostInteractionState> {
  return apiPostEncrypted<
    PublicPostInteractionPayload,
    PublicPostInteractionState
  >(
    `/public/posts/${encodeURIComponent(slug)}/view`,
    payload,
    'content-v1',
    { encryptionScope: 'public', encryptRequest: true, signal: options.signal },
  )
}

export function setPublicPostLike(
  slug: string,
  payload: PublicPostLikePayload,
  options: { signal?: AbortSignal } = {},
): Promise<PublicPostInteractionState> {
  return apiPostEncrypted<PublicPostLikePayload, PublicPostInteractionState>(
    `/public/posts/${encodeURIComponent(slug)}/like`,
    payload,
    'content-v1',
    { encryptionScope: 'public', encryptRequest: true, signal: options.signal },
  )
}

export function getPublicPage(
  slug: string,
  options: { signal?: AbortSignal } = {},
): Promise<PublicPageDetail> {
  return apiGetEncrypted<PublicPageDetail>(
    `/public/pages/${encodeURIComponent(slug)}`,
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
  )
}

export function listPublicCategories(
  params: { limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<PublicTaxonomyListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))

  return apiGetEncrypted<PublicTaxonomyListResponse>(
    `/public/categories?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public', signal: params.signal },
  )
}

export function getPublicCategory(
  slug: string,
  options: { signal?: AbortSignal } = {},
): Promise<PublicTaxonomyItem> {
  return apiGetEncrypted<PublicTaxonomyItem>(
    `/public/categories/${encodeURIComponent(slug)}`,
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
  )
}

export function listPublicTags(
  params: { limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<PublicTaxonomyListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))

  return apiGetEncrypted<PublicTaxonomyListResponse>(
    `/public/tags?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public', signal: params.signal },
  )
}

export function getPublicTag(
  slug: string,
  options: { signal?: AbortSignal } = {},
): Promise<PublicTaxonomyItem> {
  return apiGetEncrypted<PublicTaxonomyItem>(
    `/public/tags/${encodeURIComponent(slug)}`,
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
  )
}
