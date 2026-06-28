import {
  apiDeleteEncrypted,
  apiGetEncrypted,
  apiPatchEncrypted,
} from '../../api/client.ts'

import type {
  AdminCommentItem,
  AdminCommentListResponse,
  AdminCommentReviewPayload,
  AdminCommentStatusFilter,
} from './types.ts'

export function listAdminComments(
  params: {
    status?: AdminCommentStatusFilter
    limit?: number
    offset?: number
    signal?: AbortSignal
  } = {},
): Promise<AdminCommentListResponse> {
  const query = new URLSearchParams()
  query.set('status', params.status ?? 'pending')
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))
  return apiGetEncrypted<AdminCommentListResponse>(
    `/admin/comments?${query.toString()}`,
    'content-v1',
    { signal: params.signal },
  )
}

export function reviewAdminComment(
  commentId: number,
  payload: AdminCommentReviewPayload,
  csrfToken: string,
): Promise<AdminCommentItem> {
  return apiPatchEncrypted<AdminCommentReviewPayload, AdminCommentItem>(
    `/admin/comments/${commentId}/review`,
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function deleteAdminComment(
  commentId: number,
  csrfToken: string,
): Promise<AdminCommentItem> {
  return apiDeleteEncrypted<AdminCommentItem>(
    `/admin/comments/${commentId}`,
    'content-v1',
    { csrfToken },
  )
}
