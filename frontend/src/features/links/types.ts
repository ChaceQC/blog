export type AdminFriendLinkStatus = 'pending' | 'healthy' | 'rejected'
export type AdminSiteNavOpenTarget = 'blank' | 'self'
export type AdminSiteNavVisibility = 'public' | 'hidden' | 'private'

export type AdminFriendLink = {
  id: number
  group_id: number | null
  group_name: string | null
  name: string
  url: string
  avatar_url: string | null
  description: string | null
  rss_url: string | null
  status: AdminFriendLinkStatus
  sort_order: number
  last_checked_at: string | null
  last_status_code: number | null
  created_at: string | null
  updated_at: string | null
}

export type AdminFriendLinkListResponse = {
  items: AdminFriendLink[]
}

export type FriendLinkReviewPayload = {
  status: AdminFriendLinkStatus
}

export type FriendLinkWritePayload = {
  group_id: number | null
  name: string
  url: string
  avatar_url: string | null
  description: string | null
  rss_url: string | null
  status: AdminFriendLinkStatus
  sort_order: number
}

export type AdminSiteNavItem = {
  id: number
  group_id: number | null
  group_name: string | null
  group_slug: string | null
  title: string
  url: string
  icon_url: string | null
  description: string | null
  tags_json: Record<string, unknown> | null
  open_target: AdminSiteNavOpenTarget
  visibility: AdminSiteNavVisibility
  click_count: number
  sort_order: number
  created_at: string | null
  updated_at: string | null
}

export type AdminSiteNavItemListResponse = {
  items: AdminSiteNavItem[]
}

export type SiteNavItemWritePayload = {
  group_id: number | null
  title: string
  url: string
  icon_url: string | null
  description: string | null
  tags_json: Record<string, unknown> | null
  open_target: AdminSiteNavOpenTarget
  visibility: AdminSiteNavVisibility
  sort_order: number
}
