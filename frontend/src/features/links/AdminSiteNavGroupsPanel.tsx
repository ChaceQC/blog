import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FolderPlus, Save } from 'lucide-react'
import { useMemo, useState } from 'react'

import { invalidateSiteNavCaches } from '../../app/queryInvalidation.ts'
import { emptyToNull } from '../../utils/formText.ts'
import { createAdminSiteNavGroup, updateAdminSiteNavGroup } from './api.ts'
import { useAuth } from '../auth/useAuth.ts'

import type {
  AdminSiteNavGroup,
  AdminSiteNavVisibility,
  SiteNavGroupWritePayload,
} from './types.ts'

type SiteNavGroupForm = {
  name: string
  slug: string
  description: string
  visibility: AdminSiteNavVisibility
  sortOrder: number
}

type AdminSiteNavGroupsPanelProps = {
  groups: AdminSiteNavGroup[]
  isLoading: boolean
}

const emptyGroupForm: SiteNavGroupForm = {
  name: '',
  slug: '',
  description: '',
  visibility: 'public',
  sortOrder: 0,
}

export function AdminSiteNavGroupsPanel({
  groups,
  isLoading,
}: AdminSiteNavGroupsPanelProps) {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [draftForm, setDraftForm] = useState<SiteNavGroupForm | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const selectedGroup = useMemo(
    () =>
      groups.find((group) => group.id === selectedGroupId) ?? groups[0] ?? null,
    [groups, selectedGroupId],
  )
  const loadedForm = useMemo(
    () => (selectedGroup ? groupToForm(selectedGroup) : emptyGroupForm),
    [selectedGroup],
  )
  const form = draftForm ?? loadedForm
  const isCreating = selectedGroupId === null && draftForm !== null
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      const payload = formToPayload(form)
      if (isCreating || !selectedGroup) {
        return createAdminSiteNavGroup(payload, session.csrfToken)
      }
      return updateAdminSiteNavGroup(selectedGroup.id, payload, session.csrfToken)
    },
    onSuccess: (group) => {
      setSelectedGroupId(group.id)
      setDraftForm(null)
      void invalidateSiteNavCaches(queryClient)
      setNotice(isCreating ? '分组已创建' : '分组已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '分组保存失败')
    },
  })

  return (
    <div className="admin-inline-section">
      <div className="section-heading">
        <span>导航分组</span>
        <button
          className="text-button text-button--muted"
          onClick={() => {
            setSelectedGroupId(null)
            setDraftForm(emptyGroupForm)
            setNotice('正在新建分组')
          }}
          type="button"
        >
          <FolderPlus size={14} strokeWidth={1.8} aria-hidden="true" />
          新建分组
        </button>
      </div>
      <p className="empty-state">
        {notice ?? (isLoading ? '分组加载中。' : `${groups.length} 个分组`)}
      </p>
      <div className="admin-stack-list admin-stack-list--compact">
        {groups.map((group) => (
          <button
            className={group.id === selectedGroup?.id ? 'active' : undefined}
            key={group.id}
            onClick={() => {
              setSelectedGroupId(group.id)
              setDraftForm(null)
              setNotice(null)
            }}
            type="button"
          >
            <span>
              <strong>{group.name}</strong>
              <small>{group.slug}</small>
            </span>
            <small>{group.visibility === 'public' ? '公开' : '收起'}</small>
          </button>
        ))}
      </div>
      {!isLoading && groups.length === 0 && !isCreating ? (
        <p className="empty-state">还没有导航分组。</p>
      ) : null}
      {selectedGroup || isCreating ? (
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
              标识
              <input
                onChange={(event) => updateForm('slug', event.target.value)}
                value={form.slug}
              />
            </label>
          </div>
          <label>
            描述
            <textarea
              onChange={(event) => updateForm('description', event.target.value)}
              rows={2}
              value={form.description}
            />
          </label>
          <div className="form-grid form-grid--two">
            <label>
              可见性
              <select
                onChange={(event) =>
                  updateForm(
                    'visibility',
                    event.target.value as AdminSiteNavVisibility,
                  )
                }
                value={form.visibility}
              >
                <option value="public">公开</option>
                <option value="hidden">隐藏</option>
                <option value="private">后台可见</option>
              </select>
            </label>
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
          </div>
          <div className="form-actions">
            <button
              className="text-button"
              disabled={
                !session ||
                saveMutation.isPending ||
                form.name.trim() === '' ||
                form.slug.trim() === ''
              }
              onClick={() => saveMutation.mutate()}
              type="button"
            >
              <Save size={17} strokeWidth={1.8} aria-hidden="true" />
              {saveMutation.isPending ? '保存中' : '保存分组'}
            </button>
          </div>
        </form>
      ) : null}
    </div>
  )

  function updateForm<Key extends keyof SiteNavGroupForm>(
    key: Key,
    value: SiteNavGroupForm[Key],
  ) {
    setDraftForm((current) => ({ ...(current ?? form), [key]: value }))
  }
}

function groupToForm(group: AdminSiteNavGroup): SiteNavGroupForm {
  return {
    name: group.name,
    slug: group.slug,
    description: group.description ?? '',
    visibility: group.visibility,
    sortOrder: group.sort_order,
  }
}

function formToPayload(form: SiteNavGroupForm): SiteNavGroupWritePayload {
  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    description: emptyToNull(form.description),
    visibility: form.visibility,
    sort_order: Number.isFinite(form.sortOrder) ? form.sortOrder : 0,
  }
}
