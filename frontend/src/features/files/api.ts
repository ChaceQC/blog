import {
  apiDeleteEncrypted,
  apiGetEncrypted,
  apiPostFormEncrypted,
} from '../../api/client.ts'

import type {
  AdminFileItem,
  AdminFileListResponse,
  FileVisibility,
} from './types.ts'

export function listAdminFiles(): Promise<AdminFileListResponse> {
  return apiGetEncrypted<AdminFileListResponse>('/admin/files', 'content-v1')
}

export function uploadAdminFile(
  file: File,
  visibility: FileVisibility,
  altText: string,
  csrfToken: string,
): Promise<AdminFileItem> {
  const body = new FormData()
  body.append('file', file)
  body.append('visibility', visibility)
  if (altText.trim()) {
    body.append('alt_text', altText.trim())
  }

  return apiPostFormEncrypted<AdminFileItem>('/admin/files', body, 'content-v1', {
    csrfToken,
  })
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
