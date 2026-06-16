import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, SlidersHorizontal } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  listAdminSettings,
  SITE_PROFILE_SETTING_KEY,
  updateAdminSetting,
} from '../../features/settings/api.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

type SiteSettingForm = {
  title: string
  owner: string
  avatarUrl: string
  description: string
  quote: string
}

const initialForm: SiteSettingForm = {
  title: siteSettings.title,
  owner: siteSettings.owner,
  avatarUrl: siteSettings.avatarUrl,
  description: siteSettings.description,
  quote: siteSettings.quote,
}

export function AdminSettingsPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [draftForm, setDraftForm] = useState<SiteSettingForm | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const { data, isError, isLoading } = useQuery({
    queryKey: ['admin-settings'],
    queryFn: listAdminSettings,
  })
  const siteProfileSetting = useMemo(
    () =>
      data?.items.find(
        (setting) => setting.key_name === SITE_PROFILE_SETTING_KEY,
      ) ?? null,
    [data],
  )
  const loadedForm = useMemo(
    () =>
      siteProfileSetting
        ? settingToForm(siteProfileSetting.value_json)
        : initialForm,
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
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setNotice('设置已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>偏好</span>
        <h1>站点资料</h1>
        <button
          className="text-button admin-heading__action"
          disabled={!session || saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
          type="button"
        >
          <Save size={17} strokeWidth={1.8} aria-hidden="true" />
          {saveMutation.isPending ? '保存中' : '保存设置'}
        </button>
      </section>

      <div className="admin-workspace admin-workspace--two">
        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>公开资料</span>
            <small>{notice ?? (isLoading ? '加载中' : '正在使用')}</small>
          </div>
          {isError ? <p className="form-error">设置加载失败</p> : null}
          <form className="content-form">
            <div className="form-grid form-grid--two">
              <label>
                站点标题
                <input
                  onChange={(event) => updateForm('title', event.target.value)}
                  value={form.title}
                />
              </label>
              <label>
                站点所有者
                <input
                  onChange={(event) => updateForm('owner', event.target.value)}
                  value={form.owner}
                />
              </label>
            </div>
            <label>
              头像 URL
              <input
                onChange={(event) => updateForm('avatarUrl', event.target.value)}
                value={form.avatarUrl}
              />
            </label>
            <label>
              首页描述
              <textarea
                onChange={(event) => updateForm('description', event.target.value)}
                rows={3}
                value={form.description}
              />
            </label>
            <label>
              引文
              <textarea
                onChange={(event) => updateForm('quote', event.target.value)}
                rows={2}
                value={form.quote}
              />
            </label>
          </form>
        </section>

        <section className="admin-panel admin-panel--preview">
          <div className="section-heading">
            <span>设置预览</span>
            <small>
              <SlidersHorizontal size={14} strokeWidth={1.8} aria-hidden="true" />
              当前值
            </small>
          </div>
          <div className="settings-preview">
            <img src={form.avatarUrl} alt={`${form.owner} 的头像`} />
            <span>
              <strong>{form.title}</strong>
              <small>{form.owner}</small>
            </span>
            <p>{form.description}</p>
            <small>{form.quote}</small>
          </div>
          <div className="admin-note-list">
            {siteSettings.socialLinks.map((link) => (
              <p key={link.label}>
                {link.label}：{link.url}
              </p>
            ))}
          </div>
        </section>
      </div>

    </div>
  )

  function updateForm<Key extends keyof SiteSettingForm>(
    key: Key,
    value: SiteSettingForm[Key],
  ) {
    setDraftForm((current) => ({ ...(current ?? form), [key]: value }))
  }
}

function settingToForm(value: Record<string, unknown>): SiteSettingForm {
  return {
    title: stringValue(value.title, initialForm.title),
    owner: stringValue(value.owner, initialForm.owner),
    avatarUrl: stringValue(value.avatar_url, initialForm.avatarUrl),
    description: stringValue(value.description, initialForm.description),
    quote: stringValue(value.quote, initialForm.quote),
  }
}

function formToSettingValue(form: SiteSettingForm): Record<string, unknown> {
  return {
    title: form.title,
    owner: form.owner,
    avatar_url: form.avatarUrl,
    description: form.description,
    quote: form.quote,
  }
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback
}
