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
  seo_keywords: string | null
  category_names: string[]
  tag_names: string[]
  published_at: string | null
  updated_at: string | null
}

export type PublicPostDetail = PublicPostItem & {
  content_html: string
}

export type PublicPageDetail = {
  id: number
  title: string
  slug: string
  content_html: string
  seo_title: string | null
  seo_description: string | null
  updated_at: string | null
}

export type PublicPostListResponse = {
  items: PublicPostItem[]
  total: number
}

export type PublicTaxonomyItem = {
  id: number
  name: string
  slug: string
  post_count: number
}

export type PublicTaxonomyListResponse = {
  items: PublicTaxonomyItem[]
}
