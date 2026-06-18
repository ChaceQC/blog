import { siteSettings } from './siteSettings.ts'

import type { AdminSettingItem, SiteMusing, SiteSocialLink } from './types.ts'

export type SiteSettingForm = {
  title: string
  owner: string
  avatarUrl: string
  description: string
  quote: string
  musings: SiteMusing[]
  socialLinks: SiteSocialLink[]
}

export const initialSiteSettingForm: SiteSettingForm = {
  title: siteSettings.title,
  owner: siteSettings.owner,
  avatarUrl: siteSettings.avatarUrl,
  description: siteSettings.description,
  quote: siteSettings.quote,
  musings: siteSettings.musings,
  socialLinks: siteSettings.socialLinks,
}

export function settingToForm(
  setting: AdminSettingItem | null,
): SiteSettingForm {
  if (!setting) {
    return initialSiteSettingForm
  }
  return valueToForm(setting.value_json)
}

export function formToSettingValue(
  form: SiteSettingForm,
): Record<string, unknown> {
  return {
    title: form.title,
    owner: form.owner,
    avatar_url: form.avatarUrl,
    description: form.description,
    quote: form.quote,
    musings: form.musings
      .map((musing) => ({
        content: musing.content.trim(),
        date: musing.date.trim(),
      }))
      .filter((musing) => musing.content.length > 0),
    social_links: form.socialLinks
      .map((link) => ({
        label: link.label.trim(),
        url: link.url.trim(),
      }))
      .filter((link) => link.label.length > 0 && link.url.length > 0)
      .slice(0, 12),
  }
}

function valueToForm(value: Record<string, unknown>): SiteSettingForm {
  return {
    title: stringValue(value.title, initialSiteSettingForm.title),
    owner: stringValue(value.owner, initialSiteSettingForm.owner),
    avatarUrl: stringValue(value.avatar_url, initialSiteSettingForm.avatarUrl),
    description: stringValue(
      value.description,
      initialSiteSettingForm.description,
    ),
    quote: stringValue(value.quote, initialSiteSettingForm.quote),
    musings: musingsValue(value.musings),
    socialLinks: socialLinksValue(value.social_links),
  }
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback
}

function musingsValue(value: unknown): SiteMusing[] {
  if (!Array.isArray(value)) {
    return initialSiteSettingForm.musings
  }

  const musings = value
    .filter(
      (item): item is Record<string, unknown> =>
        typeof item === 'object' && item !== null,
    )
    .map((item) => ({
      content: stringValue(item.content, ''),
      date: stringValue(item.date, ''),
    }))
    .filter((musing) => musing.content.trim().length > 0)
    .slice(0, 2)

  while (musings.length < 2) {
    musings.push({ content: '', date: '' })
  }
  return musings
}

function socialLinksValue(value: unknown): SiteSocialLink[] {
  if (!Array.isArray(value)) {
    return initialSiteSettingForm.socialLinks
  }

  const socialLinks = value
    .filter(
      (item): item is Record<string, unknown> =>
        typeof item === 'object' && item !== null,
    )
    .map((item) => ({
      label: stringValue(item.label, ''),
      url: stringValue(item.url, ''),
    }))
    .filter((link) => link.label.trim().length > 0 && link.url.trim().length > 0)
    .slice(0, 12)

  return socialLinks.length > 0 ? socialLinks : initialSiteSettingForm.socialLinks
}
