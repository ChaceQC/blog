export type ContentStatus = 'draft' | 'published' | 'scheduled' | 'archived'

export type PostVisibility = 'public' | 'hidden' | 'private'

export type AdminPostItem = {
  id: number
  title: string
  slug: string
  summary: string | null
  content_md: string
  content_html: string
  status: ContentStatus
  visibility: PostVisibility
  author_id: number
  word_count: number
  seo_title: string | null
  seo_description: string | null
  published_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type AdminPageItem = {
  id: number
  title: string
  slug: string
  content_md: string
  content_html: string
  status: ContentStatus
  show_in_nav: boolean
  sort_order: number
  seo_title: string | null
  seo_description: string | null
  created_at: string | null
  updated_at: string | null
}

export type AdminPostListResponse = {
  items: AdminPostItem[]
}

export type PostPreviewPayload = {
  slug: string
  content_md: string
}

export type PostPreviewResponse = {
  content_html: string
}

export type AdminPageListResponse = {
  items: AdminPageItem[]
}

export type PostFormPayload = {
  title: string
  slug: string
  summary: string | null
  content_md: string
  status: ContentStatus
  visibility: PostVisibility
  seo_title: string | null
  seo_description: string | null
}

export type PageFormPayload = {
  title: string
  slug: string
  content_md: string
  status: ContentStatus
  show_in_nav: boolean
  sort_order: number
  seo_title: string | null
  seo_description: string | null
}
