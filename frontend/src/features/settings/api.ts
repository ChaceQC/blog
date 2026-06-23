import { apiGetEncrypted } from '../../api/client.ts'

import type { PublicSiteProfile } from './types.ts'

export function getPublicSiteProfile(
  options: { signal?: AbortSignal } = {},
): Promise<PublicSiteProfile> {
  return apiGetEncrypted<PublicSiteProfile>(
    '/public/settings/site-profile',
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
  )
}
