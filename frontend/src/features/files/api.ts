import {
  apiDeleteEncrypted,
  apiGetEncrypted,
  apiPostFormEncrypted,
} from '../../api/client.ts'
import { API_BASE_URL } from '../../api/config.ts'

import type {
  AdminFileItem,
  AdminFileListResponse,
  AdminFileTemporaryUrlResponse,
  FileVisibility,
  PublicFileListResponse,
} from './types.ts'

type PublicFileListOptions = {
  limit?: number
  offset?: number
}

export function listAdminFiles(): Promise<AdminFileListResponse> {
  return apiGetEncrypted<AdminFileListResponse>('/admin/files', 'content-v1')
}

export function uploadAdminFile(
  file: File,
  visibility: FileVisibility,
  altText: string,
  publicListed: boolean,
  csrfToken: string,
): Promise<AdminFileItem> {
  const body = new FormData()
  body.append('file', file)
  body.append('visibility', visibility)
  body.append('public_listed', publicListed ? 'true' : 'false')
  if (altText.trim()) {
    body.append('alt_text', altText.trim())
  }

  return apiPostFormEncrypted<AdminFileItem>('/admin/files', body, 'content-v1', {
    csrfToken,
  })
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
    },
  )
}

export function getPublicFileTemporaryUrl(
  fileId: number,
): Promise<AdminFileTemporaryUrlResponse> {
  return apiGetEncrypted<AdminFileTemporaryUrlResponse>(
    `/public/files/${fileId}/temporary-url`,
    'content-v1',
    { encryptionScope: 'public' },
  )
}

export function deleteAdminFile(
  fileId: number,
  csrfToken: string,
): Promise<AdminFileItem> {
  return apiDeleteEncrypted<AdminFileItem>(
    `/admin/files/${fileId}`,
    'content-v1',
    { csrfToken },
  )
}

export function getAdminFileTemporaryUrl(
  fileId: number,
): Promise<AdminFileTemporaryUrlResponse> {
  return apiGetEncrypted<AdminFileTemporaryUrlResponse>(
    `/admin/files/${fileId}/temporary-url`,
    'content-v1',
  )
}

export function adminFileThumbnailUrl(fileId: number): string {
  return `${API_BASE_URL}/admin/files/${fileId}/thumbnail`
}

export function adminFileDownloadUrl(fileId: number): string {
  return `${API_BASE_URL}/admin/files/${fileId}/download`
}
