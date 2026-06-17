import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircle2,
  ExternalLink,
  Link2,
  Save,
  XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { StatusBadge } from '../../components/StatusBadge.tsx'
import { AdminSiteNavPanel } from '../../features/links/AdminSiteNavPanel.tsx'
import {
  createAdminFriendLink,
  listAdminFriendLinks,
  reviewAdminFriendLink,
  updateAdminFriendLink,
} from '../../features/links/api.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type {
  AdminFriendLink,
  AdminFriendLinkStatus,
  FriendLinkWritePayload,
} from '../../features/links/types.ts'

const LIST_PAGE_SIZE = 8

const linkStatusLabels = {
  healthy: '通过',
  pending: '待审核',
  rejected: '已拒绝',
} satisfies Record<AdminFriendLinkStatus, string>

type FriendLinkForm = {
  name: string
  url: string
  avatarUrl: string
  description: string
  rssUrl: string
  status: AdminFriendLinkStatus
  sortOrder: number
}

const emptyForm: FriendLinkForm = {
  name: '',
  url: '',
  avatarUrl: '',
  description: '',
  rssUrl: '',
  status: 'pending',
  sortOrder: 0,
}

export function AdminLinksPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null)
  const [draftForm, setDraftForm] = useState<FriendLinkForm | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const linksQuery = useQuery({
    queryKey: ['admin-friend-links'],
    queryFn: listAdminFriendLinks,
  })
  const links = useMemo(() => linksQuery.data?.items ?? [], [linksQuery.data])
  const safeListPage = Math.min(
    listPage,
    Math.max(0, Math.ceil(links.length / LIST_PAGE_SIZE) - 1),
  )
  const visibleLinks = useMemo(
    () =>
      links.slice(
        safeListPage * LIST_PAGE_SIZE,
        safeListPage * LIST_PAGE_SIZE + LIST_PAGE_SIZE,
      ),
    [links, safeListPage],
  )
  const selectedLink = useMemo(
    () =>
      links.find((link) => link.id === selectedLinkId) ?? links[0] ?? null,
    [links, selectedLinkId],
  )
  const loadedForm = useMemo(
    () => (selectedLink ? linkToForm(selectedLink) : emptyForm),
    [selectedLink],
  )
  const form = draftForm ?? loadedForm
  const isCreating = selectedLinkId === null && draftForm !== null
  const reviewMutation = useMutation({
    mutationFn: async (status: AdminFriendLinkStatus) => {
      if (!session || !selectedLink) {
        throw new Error('当前会话已失效')
      }
      return reviewAdminFriendLink(selectedLink.id, { status }, session.csrfToken)
    },
    onSuccess: (link) => {
      setSelectedLinkId(link.id)
      queryClient.invalidateQueries({ queryKey: ['admin-friend-links'] })
      setNotice('审核状态已更新')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '审核更新失败')
    },
  })
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      const payload = formToPayload(form, selectedLink)
      if (isCreating || !selectedLink) {
        return createAdminFriendLink(payload, session.csrfToken)
      }
      return updateAdminFriendLink(selectedLink.id, payload, session.csrfToken)
    },
    onSuccess: (link) => {
      setSelectedLinkId(link.id)
      setDraftForm(null)
      queryClient.invalidateQueries({ queryKey: ['admin-friend-links'] })
      setNotice(isCreating ? '友链已创建' : '友链已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>往来</span>
        <h1>友链与导航</h1>
        <button
          className="text-button admin-heading__action"
          onClick={() => {
            setSelectedLinkId(null)
            setDraftForm(emptyForm)
            setNotice('正在新建友链')
          }}
          type="button"
        >
          <Link2 size={17} strokeWidth={1.8} aria-hidden="true" />
          新建友链
        </button>
      </section>

      <div className="admin-workspace">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>友链审核</span>
            <small>{linksQuery.isLoading ? '加载中' : `共 ${links.length} 条`}</small>
          </div>
          {linksQuery.isError ? <p className="form-error">友链列表加载失败</p> : null}
          <div className="content-list">
            {visibleLinks.map((link) => (
              <button
                className={
                  link.id === selectedLink?.id ? 'content-row active' : 'content-row'
                }
                key={link.id}
                onClick={() => {
                  setSelectedLinkId(link.id)
                  setDraftForm(null)
                  setNotice(null)
                }}
                type="button"
              >
                <span>
                  <strong>{link.name}</strong>
                  <small>{link.url}</small>
                  <small>{formatFriendLinkCheck(link)}</small>
                </span>
                <StatusBadge tone={link.status}>{linkStatusLabels[link.status]}</StatusBadge>
              </button>
            ))}
          </div>
          <ListPager
            page={safeListPage}
            pageSize={LIST_PAGE_SIZE}
            totalItems={links.length}
            isLoading={linksQuery.isLoading}
            variant="admin"
            onPageChange={setListPage}
          />
          {!linksQuery.isLoading && links.length === 0 ? (
            <p className="empty-state">还没有待管理的友链。</p>
          ) : null}
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>{isCreating ? '新建友链' : '友链编辑'}</span>
            <small>{notice ?? selectedLink?.group_name ?? '未分组'}</small>
          </div>
          {selectedLink || isCreating ? (
            <div className="admin-detail">
              <div className="admin-title-row">
                <span>
                  <strong>{form.name || '未命名友链'}</strong>
                  <small>{form.description || '暂无描述'}</small>
                </span>
                <a className="icon-button" href={form.url || '#'} aria-label="打开友链">
                  <ExternalLink size={17} strokeWidth={1.8} aria-hidden="true" />
                </a>
              </div>
              <form className="content-form">
                <div className="form-grid form-grid--two">
                  <label>
                    名称
                    <input
                      onChange={(event) => updateForm('name', event.target.value)}
                      value={form.name}
                    />
                  </label>
                  <label>
                    状态
                    <select
                      onChange={(event) =>
                        updateForm(
                          'status',
                          event.target.value as AdminFriendLinkStatus,
                        )
                      }
                      value={form.status}
                    >
                      <option value="pending">待审核</option>
                      <option value="healthy">通过</option>
                      <option value="rejected">已拒绝</option>
                    </select>
                  </label>
                </div>
                <label>
                  站点 URL
                  <input
                    onChange={(event) => updateForm('url', event.target.value)}
                    value={form.url}
                  />
                </label>
                <label>
                  描述
                  <textarea
                    onChange={(event) =>
                      updateForm('description', event.target.value)
                    }
                    rows={3}
                    value={form.description}
                  />
                </label>
                <div className="form-grid form-grid--two">
                  <label>
                    头像 URL
                    <input
                      onChange={(event) =>
                        updateForm('avatarUrl', event.target.value)
                      }
                      value={form.avatarUrl}
                    />
                  </label>
                  <label>
                    RSS URL
                    <input
                      onChange={(event) => updateForm('rssUrl', event.target.value)}
                      value={form.rssUrl}
                    />
                  </label>
                </div>
                <label>
                  排序
                  <input
                    min={0}
                    onChange={(event) =>
                      updateForm('sortOrder', Number(event.target.value))
                    }
                    type="number"
                    value={form.sortOrder}
                  />
                </label>
              </form>
              {selectedLink ? (
                <dl className="detail-list">
                  <div>
                    <dt>状态检查</dt>
                    <dd>{formatFriendLinkCheck(selectedLink)}</dd>
                  </div>
                  <div>
                    <dt>最近检查</dt>
                    <dd>{formatDateTime(selectedLink.last_checked_at)}</dd>
                  </div>
                </dl>
              ) : null}
              <div className="form-actions">
                <button
                  className="text-button"
                  disabled={!session || saveMutation.isPending || form.name === ''}
                  onClick={() => saveMutation.mutate()}
                  type="button"
                >
                  <Save size={17} strokeWidth={1.8} aria-hidden="true" />
                  {saveMutation.isPending ? '保存中' : '保存'}
                </button>
                <button
                  className="text-button"
                  disabled={!session || !selectedLink || reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate('healthy')}
                  type="button"
                >
                  <CheckCircle2 size={17} strokeWidth={1.8} aria-hidden="true" />
                  通过
                </button>
                <button
                  className="text-button text-button--muted"
                  disabled={!session || !selectedLink || reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate('rejected')}
                  type="button"
                >
                  <XCircle size={17} strokeWidth={1.8} aria-hidden="true" />
                  拒绝
                </button>
              </div>
            </div>
          ) : (
            <p className="empty-state">没有选中的友链。</p>
          )}
        </section>

        <AdminSiteNavPanel />
      </div>
    </div>
  )

  function updateForm<Key extends keyof FriendLinkForm>(
    key: Key,
    value: FriendLinkForm[Key],
  ) {
    setDraftForm((current) => ({ ...(current ?? form), [key]: value }))
  }

}

function linkToForm(link: AdminFriendLink): FriendLinkForm {
  return {
    name: link.name,
    url: link.url,
    avatarUrl: link.avatar_url ?? '',
    description: link.description ?? '',
    rssUrl: link.rss_url ?? '',
    status: link.status,
    sortOrder: link.sort_order,
  }
}

function formToPayload(
  form: FriendLinkForm,
  link: AdminFriendLink | null,
): FriendLinkWritePayload {
  return {
    group_id: link?.group_id ?? null,
    name: form.name,
    url: form.url,
    avatar_url: emptyToNull(form.avatarUrl),
    description: emptyToNull(form.description),
    rss_url: emptyToNull(form.rssUrl),
    status: form.status,
    sort_order: Number.isFinite(form.sortOrder) ? form.sortOrder : 0,
  }
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function formatFriendLinkCheck(link: AdminFriendLink): string {
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

function formatDateTime(value: string | null): string {
  if (!value) {
    return '未记录'
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value))
}
