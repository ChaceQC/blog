import { apiGetEncrypted, apiPostEncrypted } from '../../api/client.ts'

import type {
  PublicFriendLinkApplicationPayload,
  PublicFriendLinkApplicationResponse,
  PublicFriendLinkListResponse,
} from './types.ts'

type PublicLinkListOptions = {
  limit?: number
  offset?: number
  signal?: AbortSignal
}

export function listPublicFriendLinks(
  options: PublicLinkListOptions = {},
): Promise<PublicFriendLinkListResponse> {
  const query = buildPublicListQuery(options)
  return apiGetEncrypted<PublicFriendLinkListResponse>(
    `/public/friend-links${query}`,
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
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
