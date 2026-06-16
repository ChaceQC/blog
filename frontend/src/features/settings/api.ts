import { apiGetEncrypted, apiPatchEncrypted } from '../../api/client.ts'

import type {
  AdminSettingItem,
  AdminSettingListResponse,
  PublicSiteProfile,
  SettingUpdatePayload,
} from './types.ts'

export const SITE_PROFILE_SETTING_KEY = 'site_profile'

export function listAdminSettings(): Promise<AdminSettingListResponse> {
  return apiGetEncrypted<AdminSettingListResponse>(
    '/admin/settings',
    'sensitive-v1',
  )
}

export function updateAdminSetting(
  keyName: string,
  payload: SettingUpdatePayload,
  csrfToken: string,
): Promise<AdminSettingItem> {
  return apiPatchEncrypted<SettingUpdatePayload, AdminSettingItem>(
    `/admin/settings/${keyName}`,
    payload,
    'sensitive-v1',
    { csrfToken, encryptRequest: true },
  )
}

export function getPublicSiteProfile(): Promise<PublicSiteProfile> {
  return apiGetEncrypted<PublicSiteProfile>(
    '/public/settings/site-profile',
    'content-v1',
    { encryptionScope: 'public' },
  )
}
