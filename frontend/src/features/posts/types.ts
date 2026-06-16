export type PublicPostItem = {
  id: number
  title: string
  slug: string
  summary: string | null
  cover_file_id: number | null
  cover_image_url: string | null
  word_count: number
  seo_title: string | null
  seo_description: string | null
  published_at: string | null
  updated_at: string | null
}

export type PublicPostDetail = PublicPostItem & {
  content_html: string
}

export type PublicPostListResponse = {
  items: PublicPostItem[]
}
