import { apiGetEncrypted } from '../../api/client.ts'

import type { PublicSiteNavItemListResponse } from './types.ts'

type PublicSiteListOptions = {
  limit?: number
  offset?: number
}

export function listPublicSiteItems(
  options: PublicSiteListOptions = {},
): Promise<PublicSiteNavItemListResponse> {
  const params = new URLSearchParams()
  if (options.limit !== undefined) {
    params.set('limit', String(options.limit))
  }
  if (options.offset !== undefined) {
    params.set('offset', String(options.offset))
  }
  const query = params.toString()

  return apiGetEncrypted<PublicSiteNavItemListResponse>(
    `/public/site-items${query ? `?${query}` : ''}`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}
