import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigation, Save } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  createAdminSiteNavItem,
  listAdminSiteNavItems,
  updateAdminSiteNavItem,
} from './api.ts'
import { useAuth } from '../auth/useAuth.ts'

import type {
  AdminSiteNavItem,
  AdminSiteNavOpenTarget,
  AdminSiteNavVisibility,
  SiteNavItemWritePayload,
} from './types.ts'

type SiteNavForm = {
  title: string
  url: string
  iconUrl: string
  description: string
  openTarget: AdminSiteNavOpenTarget
  visibility: AdminSiteNavVisibility
  sortOrder: number
}

const emptySiteForm: SiteNavForm = {
  title: '',
  url: '',
  iconUrl: '',
  description: '',
  openTarget: 'blank',
  visibility: 'public',
  sortOrder: 0,
}

export function AdminSiteNavPanel() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null)
  const [siteDraftForm, setSiteDraftForm] = useState<SiteNavForm | null>(null)
  const [siteNotice, setSiteNotice] = useState<string | null>(null)
  const sitesQuery = useQuery({
    queryKey: ['admin-site-nav-items'],
    queryFn: listAdminSiteNavItems,
  })
  const sites = useMemo(() => sitesQuery.data?.items ?? [], [sitesQuery.data])
  const selectedSite = useMemo(
    () =>
      sites.find((site) => site.id === selectedSiteId) ?? sites[0] ?? null,
    [sites, selectedSiteId],
  )
  const loadedSiteForm = useMemo(
    () => (selectedSite ? siteToForm(selectedSite) : emptySiteForm),
    [selectedSite],
  )
  const siteForm = siteDraftForm ?? loadedSiteForm
  const isCreatingSite = selectedSiteId === null && siteDraftForm !== null
  const saveSiteMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      const payload = siteFormToPayload(siteForm, selectedSite)
      if (isCreatingSite || !selectedSite) {
        return createAdminSiteNavItem(payload, session.csrfToken)
      }
      return updateAdminSiteNavItem(selectedSite.id, payload, session.csrfToken)
    },
    onSuccess: (site) => {
      setSelectedSiteId(site.id)
      setSiteDraftForm(null)
      queryClient.invalidateQueries({ queryKey: ['admin-site-nav-items'] })
      setSiteNotice(isCreatingSite ? '导航已创建' : '导航已保存')
    },
    onError: (error) => {
      setSiteNotice(error instanceof Error ? error.message : '导航保存失败')
    },
  })

  return (
    <section className="admin-panel admin-panel--preview">
      <div className="section-heading">
        <span>导航条目</span>
        <button
          className="text-button text-button--muted"
          onClick={() => {
            setSelectedSiteId(null)
            setSiteDraftForm(emptySiteForm)
            setSiteNotice('正在新建导航')
          }}
          type="button"
        >
          <Navigation size={14} strokeWidth={1.8} aria-hidden="true" />
          新建导航
        </button>
      </div>
      <p className="empty-state">
        {siteNotice ?? (sitesQuery.isLoading ? '导航加载中。' : `${sites.length} 个条目`)}
      </p>
      {sitesQuery.isError ? <p className="form-error">导航条目加载失败</p> : null}
      <div className="admin-stack-list">
        {sites.map((site) => (
          <button
            className={site.id === selectedSite?.id ? 'active' : undefined}
            key={site.id}
            onClick={() => {
              setSelectedSiteId(site.id)
              setSiteDraftForm(null)
              setSiteNotice(null)
            }}
            type="button"
          >
            <span>
              <strong>{site.title}</strong>
              <small>{site.description ?? '暂无描述'}</small>
            </span>
            <small>{site.group_name ?? '未分组'}</small>
          </button>
        ))}
      </div>
      {!sitesQuery.isLoading && sites.length === 0 ? (
        <p className="empty-state">还没有导航条目。</p>
      ) : null}
      {selectedSite || isCreatingSite ? (
        <form className="content-form">
          <label>
            标题
            <input
              onChange={(event) => updateSiteForm('title', event.target.value)}
              value={siteForm.title}
            />
          </label>
          <label>
            URL
            <input
              onChange={(event) => updateSiteForm('url', event.target.value)}
              value={siteForm.url}
            />
          </label>
          <label>
            描述
            <textarea
              onChange={(event) =>
                updateSiteForm('description', event.target.value)
              }
              rows={2}
              value={siteForm.description}
            />
          </label>
          <div className="form-grid form-grid--two">
            <label>
              打开方式
              <select
                onChange={(event) =>
                  updateSiteForm(
                    'openTarget',
                    event.target.value as AdminSiteNavOpenTarget,
                  )
                }
                value={siteForm.openTarget}
              >
                <option value="blank">新窗口</option>
                <option value="self">当前页</option>
              </select>
            </label>
            <label>
              可见性
              <select
                onChange={(event) =>
                  updateSiteForm(
                    'visibility',
                    event.target.value as AdminSiteNavVisibility,
                  )
                }
                value={siteForm.visibility}
              >
                <option value="public">公开</option>
                <option value="hidden">隐藏</option>
                <option value="private">后台可见</option>
              </select>
            </label>
          </div>
          <div className="form-grid form-grid--two">
            <label>
              图标 URL
              <input
                onChange={(event) => updateSiteForm('iconUrl', event.target.value)}
                value={siteForm.iconUrl}
              />
            </label>
            <label>
              排序
              <input
                min={0}
                onChange={(event) =>
                  updateSiteForm('sortOrder', Number(event.target.value))
                }
                type="number"
                value={siteForm.sortOrder}
              />
            </label>
          </div>
          <div className="form-actions">
            <button
              className="text-button"
              disabled={
                !session || saveSiteMutation.isPending || siteForm.title === ''
              }
              onClick={() => saveSiteMutation.mutate()}
              type="button"
            >
              <Save size={17} strokeWidth={1.8} aria-hidden="true" />
              {saveSiteMutation.isPending ? '保存中' : '保存导航'}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  )

  function updateSiteForm<Key extends keyof SiteNavForm>(
    key: Key,
    value: SiteNavForm[Key],
  ) {
    setSiteDraftForm((current) => ({ ...(current ?? siteForm), [key]: value }))
  }
}

function siteToForm(site: AdminSiteNavItem): SiteNavForm {
  return {
    title: site.title,
    url: site.url,
    iconUrl: site.icon_url ?? '',
    description: site.description ?? '',
    openTarget: site.open_target,
    visibility: site.visibility,
    sortOrder: site.sort_order,
  }
}

function siteFormToPayload(
  form: SiteNavForm,
  site: AdminSiteNavItem | null,
): SiteNavItemWritePayload {
  return {
    group_id: site?.group_id ?? null,
    title: form.title,
    url: form.url,
    icon_url: emptyToNull(form.iconUrl),
    description: emptyToNull(form.description),
    tags_json: site?.tags_json ?? null,
    open_target: form.openTarget,
    visibility: form.visibility,
    sort_order: Number.isFinite(form.sortOrder) ? form.sortOrder : 0,
  }
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}
