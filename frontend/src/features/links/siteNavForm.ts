import { emptyToNull } from '../../utils/formText.ts'
import {
  siteNavTagsPayload,
  siteNavTagsToText,
} from '../sites/siteNavTags.ts'

import type {
  AdminSiteNavItem,
  AdminSiteNavOpenTarget,
  AdminSiteNavVisibility,
  SiteNavItemWritePayload,
} from './types.ts'

export type SiteNavForm = {
  groupId: number | null
  title: string
  url: string
  iconUrl: string
  description: string
  tagsText: string
  openTarget: AdminSiteNavOpenTarget
  visibility: AdminSiteNavVisibility
  sortOrder: number
}

export const emptySiteForm: SiteNavForm = {
  groupId: null,
  title: '',
  url: '',
  iconUrl: '',
  description: '',
  tagsText: '',
  openTarget: 'blank',
  visibility: 'public',
  sortOrder: 0,
}

export function siteToForm(site: AdminSiteNavItem): SiteNavForm {
  return {
    groupId: site.group_id,
    title: site.title,
    url: site.url,
    iconUrl: site.icon_url ?? '',
    description: site.description ?? '',
    tagsText: siteNavTagsToText(site.tags_json),
    openTarget: site.open_target,
    visibility: site.visibility,
    sortOrder: site.sort_order,
  }
}

export function siteFormToPayload(form: SiteNavForm): SiteNavItemWritePayload {
  return {
    group_id: form.groupId,
    title: form.title,
    url: form.url,
    icon_url: emptyToNull(form.iconUrl),
    description: emptyToNull(form.description),
    tags_json: siteNavTagsPayload(form.tagsText),
    open_target: form.openTarget,
    visibility: form.visibility,
    sort_order: Number.isFinite(form.sortOrder) ? form.sortOrder : 0,
  }
}
