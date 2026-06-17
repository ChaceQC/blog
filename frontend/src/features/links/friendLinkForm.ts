import type {
  AdminFriendLink,
  AdminFriendLinkGroup,
  AdminFriendLinkStatus,
  FriendLinkWritePayload,
} from './types.ts'

export const linkStatusLabels = {
  healthy: '通过',
  pending: '待审核',
  rejected: '已拒绝',
} satisfies Record<AdminFriendLinkStatus, string>

export type FriendLinkForm = {
  groupId: number | null
  name: string
  url: string
  avatarUrl: string
  description: string
  rssUrl: string
  status: AdminFriendLinkStatus
  sortOrder: number
}

export const emptyFriendLinkForm: FriendLinkForm = {
  groupId: null,
  name: '',
  url: '',
  avatarUrl: '',
  description: '',
  rssUrl: '',
  status: 'pending',
  sortOrder: 0,
}

export function linkToForm(link: AdminFriendLink): FriendLinkForm {
  return {
    groupId: link.group_id,
    name: link.name,
    url: link.url,
    avatarUrl: link.avatar_url ?? '',
    description: link.description ?? '',
    rssUrl: link.rss_url ?? '',
    status: link.status,
    sortOrder: link.sort_order,
  }
}

export function formToPayload(form: FriendLinkForm): FriendLinkWritePayload {
  return {
    group_id: form.groupId,
    name: form.name,
    url: form.url,
    avatar_url: emptyToNull(form.avatarUrl),
    description: emptyToNull(form.description),
    rss_url: emptyToNull(form.rssUrl),
    status: form.status,
    sort_order: Number.isFinite(form.sortOrder) ? form.sortOrder : 0,
  }
}

export function parseOptionalId(value: string): number | null {
  if (value === '') {
    return null
  }
  const parsed = Number.parseInt(value, 10)
  return Number.isNaN(parsed) ? null : parsed
}

export function groupLabel(
  groupId: number | null,
  groups: AdminFriendLinkGroup[],
): string | null {
  if (groupId === null) {
    return null
  }
  return groups.find((group) => group.id === groupId)?.name ?? null
}

export function formatFriendLinkCheck(link: AdminFriendLink): string {
  if (!link.last_checked_at) {
    return '未检查'
  }
  if (link.last_status_code === 0) {
    return `访问失败 · ${formatDateTime(link.last_checked_at)}`
  }
  if (
    link.last_status_code !== null &&
    link.last_status_code >= 200 &&
    link.last_status_code < 400
  ) {
    return `正常 ${link.last_status_code} · ${formatDateTime(link.last_checked_at)}`
  }
  return `异常 ${link.last_status_code ?? '未知'} · ${formatDateTime(link.last_checked_at)}`
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

export function formatDateTime(value: string | null): string {
  if (!value) {
    return '未记录'
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value))
}
