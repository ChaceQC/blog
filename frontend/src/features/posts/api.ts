import { apiGetEncrypted, apiPostEncrypted } from '../../api/client.ts'

import type {
  PublicPageDetail,
  PublicCommentCreatePayload,
  PublicCommentCreateResponse,
  PublicCommentDeletePayload,
  PublicCommentDeleteResponse,
  PublicCommentListResponse,
  PublicOwnedCommentsPayload,
  PublicOwnedCommentsResponse,
  PublicPostInteractionPayload,
  PublicPostInteractionState,
  PublicPostDetail,
  PublicPostListResponse,
  PublicPostLikePayload,
  PublicTaxonomyItem,
  PublicTaxonomyListResponse,
} from './types.ts'

const OWNED_COMMENT_RECEIPT_BATCH_SIZE = 50

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

export function listPublicComments(
  slug: string,
  params: { limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<PublicCommentListResponse> {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))

  return apiGetEncrypted<PublicCommentListResponse>(
    `/public/posts/${encodeURIComponent(slug)}/comments?${query.toString()}`,
    'content-v1',
    { encryptionScope: 'public', signal: params.signal },
  )
}

export function createPublicComment(
  slug: string,
  payload: PublicCommentCreatePayload,
  options: { signal?: AbortSignal } = {},
): Promise<PublicCommentCreateResponse> {
  return apiPostEncrypted<PublicCommentCreatePayload, PublicCommentCreateResponse>(
    `/public/posts/${encodeURIComponent(slug)}/comments`,
    payload,
    'content-v1',
    { encryptionScope: 'public', encryptRequest: true, signal: options.signal },
  )
}

export function listOwnedPublicComments(
  slug: string,
  payload: PublicOwnedCommentsPayload,
  options: { signal?: AbortSignal } = {},
): Promise<PublicOwnedCommentsResponse> {
  if (payload.receipts.length > OWNED_COMMENT_RECEIPT_BATCH_SIZE) {
    return listOwnedPublicCommentsInBatches(slug, payload, options)
  }
  return apiPostEncrypted<PublicOwnedCommentsPayload, PublicOwnedCommentsResponse>(
    `/public/posts/${encodeURIComponent(slug)}/comments/owned`,
    payload,
    'content-v1',
    { encryptionScope: 'public', encryptRequest: true, signal: options.signal },
  )
}

async function listOwnedPublicCommentsInBatches(
  slug: string,
  payload: PublicOwnedCommentsPayload,
  options: { signal?: AbortSignal } = {},
): Promise<PublicOwnedCommentsResponse> {
  const batches: PublicOwnedCommentsPayload[] = []
  for (
    let index = 0;
    index < payload.receipts.length;
    index += OWNED_COMMENT_RECEIPT_BATCH_SIZE
  ) {
    batches.push({
      receipts: payload.receipts.slice(
        index,
        index + OWNED_COMMENT_RECEIPT_BATCH_SIZE,
      ),
    })
  }
  const responses = await Promise.all(
    batches.map((batch) => listOwnedPublicComments(slug, batch, options)),
  )
  const items = new Map<number, PublicOwnedCommentsResponse['items'][number]>()
  for (const response of responses) {
    for (const item of response.items) {
      items.set(item.id, item)
    }
  }
  return { items: Array.from(items.values()) }
}

export function deletePublicComment(
  slug: string,
  commentId: number,
  payload: PublicCommentDeletePayload,
  options: { signal?: AbortSignal } = {},
): Promise<PublicCommentDeleteResponse> {
  return apiPostEncrypted<PublicCommentDeletePayload, PublicCommentDeleteResponse>(
    `/public/posts/${encodeURIComponent(slug)}/comments/${commentId}/delete`,
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
