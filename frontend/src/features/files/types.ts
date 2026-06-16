export type FileVisibility = 'public' | 'private'

export type AdminFileItem = {
  id: number
  storage: string
  bucket: string | null
  object_key: string
  public_url: string | null
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
  status: string
  usage_count: number
  created_at: string | null
  updated_at: string | null
}

export type AdminFileListResponse = {
  items: AdminFileItem[]
}
