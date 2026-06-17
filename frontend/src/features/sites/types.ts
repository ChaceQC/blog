export type SiteItem = {
  id: number
  group_name: string | null
  group_slug: string | null
  title: string
  url: string
  icon_url: string | null
  description: string | null
  tags_json: Record<string, unknown> | null
  open_target: 'blank' | 'self'
  sort_order: number
}

export type PublicSiteNavItemListResponse = {
  items: SiteItem[]
  total: number
}
