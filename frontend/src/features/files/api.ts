import { apiGetEncrypted } from '../../api/client.ts'

import type {
  AdminFileTemporaryUrlResponse,
  PublicFileListResponse,
} from './types.ts'

type PublicFileListOptions = {
  limit?: number
  offset?: number
  signal?: AbortSignal
}

export function listPublicFiles(
  options: PublicFileListOptions = {},
): Promise<PublicFileListResponse> {
  const params = new URLSearchParams()
  if (options.limit !== undefined) {
    params.set('limit', String(options.limit))
  }
  if (options.offset !== undefined) {
    params.set('offset', String(options.offset))
  }
  const query = params.toString()
  return apiGetEncrypted<PublicFileListResponse>(
    `/public/files${query ? `?${query}` : ''}`,
    'content-v1',
    {
      encryptionScope: 'public',
      signal: options.signal,
    },
  )
}

export function getPublicFileTemporaryUrl(
  fileId: number,
  options: { signal?: AbortSignal } = {},
): Promise<AdminFileTemporaryUrlResponse> {
  return apiGetEncrypted<AdminFileTemporaryUrlResponse>(
    `/public/files/${fileId}/temporary-url`,
    'content-v1',
    { encryptionScope: 'public', signal: options.signal },
  )
}
