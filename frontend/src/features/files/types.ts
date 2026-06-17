export type FileVisibility = 'public' | 'private'

export type AdminFileItem = {
  id: number
  storage: string
  bucket: string | null
  object_key: string
  original_name: string
  mime_type: string
  extension: string
  size_bytes: number
  sha256: string
  width: number | null
  height: number | null
  alt_text: string | null
  uploader_id: number | null
  visibility: FileVisibility
  public_listed: boolean
  status: string
  usage_count: number
  created_at: string | null
  updated_at: string | null
}

export type AdminFileListResponse = {
  items: AdminFileItem[]
}

export type AdminFileTemporaryUrlResponse = {
  url: string
  expires_at: string
}

export type PublicFileItem = {
  id: number
  original_name: string
  mime_type: string
  extension: string
  size_bytes: number
  width: number | null
  height: number | null
  alt_text: string | null
  created_at: string | null
  updated_at: string | null
}

export type PublicFileListResponse = {
  items: PublicFileItem[]
  total: number
}
