import {
  apiGetEncrypted,
  apiPatchEncrypted,
  apiPostEncrypted,
} from '../../api/client.ts'

import type {
  AdminPageItem,
  AdminPageListResponse,
  AdminPostItem,
  AdminPostListResponse,
  PageFormPayload,
  PostFormPayload,
  PostPreviewPayload,
  PostPreviewResponse,
} from './types.ts'

export function listAdminPosts(): Promise<AdminPostListResponse> {
  return apiGetEncrypted<AdminPostListResponse>(
    '/admin/posts',
    'content-v1',
  )
}

export function createAdminPost(
  payload: PostFormPayload,
  csrfToken: string,
): Promise<AdminPostItem> {
  return apiPostEncrypted<PostFormPayload, AdminPostItem>(
    '/admin/posts',
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function updateAdminPost(
  postId: number,
  payload: PostFormPayload,
  csrfToken: string,
): Promise<AdminPostItem> {
  return apiPatchEncrypted<PostFormPayload, AdminPostItem>(
    `/admin/posts/${postId}`,
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function publishAdminPost(
  postId: number,
  csrfToken: string,
): Promise<AdminPostItem> {
  return apiPostEncrypted<Record<string, never>, AdminPostItem>(
    `/admin/posts/${postId}/publish`,
    {},
    'content-v1',
    { csrfToken },
  )
}

export function previewAdminPost(
  payload: PostPreviewPayload,
  csrfToken: string,
): Promise<PostPreviewResponse> {
  return apiPostEncrypted<PostPreviewPayload, PostPreviewResponse>(
    '/admin/posts/preview',
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function listAdminPages(): Promise<AdminPageListResponse> {
  return apiGetEncrypted<AdminPageListResponse>(
    '/admin/pages',
    'content-v1',
  )
}

export function createAdminPage(
  payload: PageFormPayload,
  csrfToken: string,
): Promise<AdminPageItem> {
  return apiPostEncrypted<PageFormPayload, AdminPageItem>(
    '/admin/pages',
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function updateAdminPage(
  pageId: number,
  payload: PageFormPayload,
  csrfToken: string,
): Promise<AdminPageItem> {
  return apiPatchEncrypted<PageFormPayload, AdminPageItem>(
    `/admin/pages/${pageId}`,
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}
