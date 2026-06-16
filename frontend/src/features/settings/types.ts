export type AdminSettingItem = {
  id: number | null
  key_name: string
  value_json: Record<string, unknown>
  group_name: string
  is_public: boolean
  updated_by: number | null
  updated_at: string | null
}

export type AdminSettingListResponse = {
  items: AdminSettingItem[]
}

export type SettingUpdatePayload = {
  value_json: Record<string, unknown>
  group_name: string
  is_public: boolean
}

export type PublicSiteProfile = {
  title: string
  owner: string
  avatar_url: string
  description: string
  quote: string
  musings: SiteMusing[]
  social_links: SiteSocialLink[]
}

export type SiteMusing = {
  content: string
  date: string
}

export type SiteSocialLink = {
  label: string
  url: string
}
