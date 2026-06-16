import {
  apiGetEncrypted,
  apiPatchEncrypted,
  apiPostEncrypted,
} from '../../api/client.ts'

import type {
  AdminFriendLink,
  AdminFriendLinkListResponse,
  AdminSiteNavItem,
  AdminSiteNavItemListResponse,
  FriendLinkReviewPayload,
  FriendLinkWritePayload,
  PublicFriendLinkApplicationPayload,
  PublicFriendLinkApplicationResponse,
  PublicFriendLinkListResponse,
  SiteNavItemWritePayload,
} from './types.ts'

type PublicLinkListOptions = {
  limit?: number
  offset?: number
}

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

export function createAdminFriendLink(
  payload: FriendLinkWritePayload,
  csrfToken: string,
): Promise<AdminFriendLink> {
  return apiPostEncrypted<FriendLinkWritePayload, AdminFriendLink>(
    '/admin/friend-links',
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function updateAdminFriendLink(
  linkId: number,
  payload: FriendLinkWritePayload,
  csrfToken: string,
): Promise<AdminFriendLink> {
  return apiPatchEncrypted<FriendLinkWritePayload, AdminFriendLink>(
    `/admin/friend-links/${linkId}`,
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

export function createAdminSiteNavItem(
  payload: SiteNavItemWritePayload,
  csrfToken: string,
): Promise<AdminSiteNavItem> {
  return apiPostEncrypted<SiteNavItemWritePayload, AdminSiteNavItem>(
    '/admin/site-items',
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function updateAdminSiteNavItem(
  itemId: number,
  payload: SiteNavItemWritePayload,
  csrfToken: string,
): Promise<AdminSiteNavItem> {
  return apiPatchEncrypted<SiteNavItemWritePayload, AdminSiteNavItem>(
    `/admin/site-items/${itemId}`,
    payload,
    'content-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function listPublicFriendLinks(
  options: PublicLinkListOptions = {},
): Promise<PublicFriendLinkListResponse> {
  const query = buildPublicListQuery(options)
  return apiGetEncrypted<PublicFriendLinkListResponse>(
    `/public/friend-links${query}`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}

export function submitPublicFriendLinkApplication(
  payload: PublicFriendLinkApplicationPayload,
): Promise<PublicFriendLinkApplicationResponse> {
  return apiPostEncrypted<
    PublicFriendLinkApplicationPayload,
    PublicFriendLinkApplicationResponse
  >('/public/friend-links/applications', payload, 'content-v1', {
    encryptionScope: 'public',
    encryptRequest: true,
  })
}

function buildPublicListQuery(options: PublicLinkListOptions): string {
  const params = new URLSearchParams()
  if (options.limit !== undefined) {
    params.set('limit', String(options.limit))
  }
  if (options.offset !== undefined) {
    params.set('offset', String(options.offset))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}
