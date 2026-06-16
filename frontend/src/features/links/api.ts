import { apiGetEncrypted, apiPatchEncrypted } from '../../api/client.ts'

import type {
  AdminFriendLink,
  AdminFriendLinkListResponse,
  AdminSiteNavItemListResponse,
  FriendLinkReviewPayload,
} from './types.ts'

export function listAdminFriendLinks(): Promise<AdminFriendLinkListResponse> {
  return apiGetEncrypted<AdminFriendLinkListResponse>(
    '/admin/friend-links?limit=50',
    'content-v1',
  )
}

export function reviewAdminFriendLink(
  linkId: number,
  payload: FriendLinkReviewPayload,
  csrfToken: string,
): Promise<AdminFriendLink> {
  return apiPatchEncrypted<FriendLinkReviewPayload, AdminFriendLink>(
    `/admin/friend-links/${linkId}/review`,
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function listAdminSiteNavItems(): Promise<AdminSiteNavItemListResponse> {
  return apiGetEncrypted<AdminSiteNavItemListResponse>(
    '/admin/site-items?limit=50',
    'content-v1',
  )
}
