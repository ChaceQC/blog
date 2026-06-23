import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { invalidateSiteProfileCaches } from '../../app/queryInvalidation.ts'
import {
  listAdminSettings,
  SITE_PROFILE_SETTING_KEY,
  updateAdminSetting,
} from './adminApi.ts'
import {
  formToSettingValue,
  settingToForm,
} from './siteProfileForm.ts'

import type { AuthSession } from '../auth/session.ts'
import type {
  SiteMusing,
  SiteSocialLink,
} from './types.ts'
import type { SiteSettingForm } from './siteProfileForm.ts'

export type SettingSection = 'profile' | 'musings' | 'social'

export const settingSectionLabels = {
  profile: '基础资料',
  musings: '首页碎念',
  social: '社交入口',
} satisfies Record<SettingSection, string>

export function useAdminSiteProfileEditor(session: AuthSession | null) {
  const queryClient = useQueryClient()
  const [draftForm, setDraftForm] = useState<SiteSettingForm | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [activeSection, setActiveSection] =
    useState<SettingSection>('profile')
  const settingsQuery = useQuery({
    queryKey: ['admin-settings'],
    queryFn: listAdminSettings,
  })
  const siteProfileSetting = useMemo(
    () =>
      settingsQuery.data?.items.find(
        (setting) => setting.key_name === SITE_PROFILE_SETTING_KEY,
      ) ?? null,
    [settingsQuery.data],
  )
  const loadedForm = useMemo(
    () => settingToForm(siteProfileSetting),
    [siteProfileSetting],
  )
  const form = draftForm ?? loadedForm

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      return updateAdminSetting(
        SITE_PROFILE_SETTING_KEY,
        {
          value_json: formToSettingValue(form),
          group_name: 'site',
          is_public: true,
        },
        session.csrfToken,
      )
    },
    onSuccess: () => {
      setDraftForm(null)
      void invalidateSiteProfileCaches(queryClient)
      setNotice('设置已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })

  function updateForm<Key extends keyof SiteSettingForm>(
    key: Key,
    value: SiteSettingForm[Key],
  ) {
    setDraftForm((current) => ({ ...(current ?? form), [key]: value }))
  }

  function updateMusing(
    index: number,
    key: keyof SiteMusing,
    value: string,
  ) {
    setDraftForm((current) => {
      const nextForm = current ?? form
      const musings = [...nextForm.musings]
      musings[index] = { ...musings[index], [key]: value }
      return { ...nextForm, musings }
    })
  }

  function updateSocialLink(
    index: number,
    key: keyof SiteSocialLink,
    value: string,
  ) {
    setDraftForm((current) => {
      const nextForm = current ?? form
      const socialLinks = [...nextForm.socialLinks]
      socialLinks[index] = { ...socialLinks[index], [key]: value }
      return { ...nextForm, socialLinks }
    })
  }

  function addSocialLink() {
    setDraftForm((current) => {
      const nextForm = current ?? form
      return {
        ...nextForm,
        socialLinks: [...nextForm.socialLinks, { label: '', url: '' }],
      }
    })
  }

  function removeSocialLink(index: number) {
    setDraftForm((current) => {
      const nextForm = current ?? form
      return {
        ...nextForm,
        socialLinks: nextForm.socialLinks.filter(
          (_, itemIndex) => itemIndex !== index,
        ),
      }
    })
  }

  return {
    activeSection,
    addSocialLink,
    form,
    isError: settingsQuery.isError,
    isLoading: settingsQuery.isLoading,
    notice,
    removeSocialLink,
    saveMutation,
    setActiveSection,
    updateForm,
    updateMusing,
    updateSocialLink,
  }
}
