import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Save, SlidersHorizontal, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  listAdminSettings,
  SITE_PROFILE_SETTING_KEY,
  updateAdminSetting,
} from '../../features/settings/api.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'
import { useAuth } from '../../features/auth/useAuth.ts'
import type {
  SiteMusing,
  SiteSocialLink,
} from '../../features/settings/types.ts'

type SiteSettingForm = {
  title: string
  owner: string
  avatarUrl: string
  description: string
  quote: string
  musings: SiteMusing[]
  socialLinks: SiteSocialLink[]
}
type SettingSection = 'profile' | 'musings' | 'social'

const settingSectionLabels = {
  profile: '基础资料',
  musings: '首页碎念',
  social: '社交入口',
} satisfies Record<SettingSection, string>

const initialForm: SiteSettingForm = {
  title: siteSettings.title,
  owner: siteSettings.owner,
  avatarUrl: siteSettings.avatarUrl,
  description: siteSettings.description,
  quote: siteSettings.quote,
  musings: siteSettings.musings,
  socialLinks: siteSettings.socialLinks,
}

export function AdminSettingsPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [draftForm, setDraftForm] = useState<SiteSettingForm | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState<SettingSection>('profile')
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
      queryClient.invalidateQueries({ queryKey: ['public-site-profile'] })
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
          <div className="admin-tabs" role="tablist" aria-label="站点资料分区">
            {(Object.keys(settingSectionLabels) as SettingSection[]).map((section) => (
              <button
                aria-selected={activeSection === section}
                className={activeSection === section ? 'admin-tab active' : 'admin-tab'}
                key={section}
                onClick={() => setActiveSection(section)}
                role="tab"
                type="button"
              >
                {settingSectionLabels[section]}
              </button>
            ))}
          </div>
          <form className="content-form">
            {activeSection === 'profile' ? (
              <>
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
              </>
            ) : null}
            {activeSection === 'musings' ? (
              <div className="field-group">
                <span className="field-label">首页碎念</span>
                <div className="musing-editor-list">
                  {form.musings.slice(0, 2).map((musing, index) => (
                    <div className="musing-editor" key={index}>
                      <label>
                        内容
                        <textarea
                          onChange={(event) =>
                            updateMusing(index, 'content', event.target.value)
                          }
                          rows={2}
                          value={musing.content}
                        />
                      </label>
                      <label>
                        日期
                        <input
                          onChange={(event) =>
                            updateMusing(index, 'date', event.target.value)
                          }
                          value={musing.date}
                        />
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {activeSection === 'social' ? (
              <div className="field-group">
                <div className="field-label-row">
                  <span className="field-label">首页社交入口</span>
                  <button
                    className="text-button text-button--muted"
                    onClick={addSocialLink}
                    type="button"
                  >
                    <Plus size={15} strokeWidth={1.8} aria-hidden="true" />
                    添加入口
                  </button>
                </div>
                <div className="musing-editor-list">
                  {form.socialLinks.map((link, index) => (
                    <div className="social-link-editor" key={index}>
                      <label>
                        名称
                        <input
                          onChange={(event) =>
                            updateSocialLink(index, 'label', event.target.value)
                          }
                          value={link.label}
                        />
                      </label>
                      <label>
                        URL
                        <input
                          onChange={(event) =>
                            updateSocialLink(index, 'url', event.target.value)
                          }
                          value={link.url}
                        />
                      </label>
                      <button
                        aria-label={`删除 ${link.label || '社交入口'}`}
                        className="icon-button social-link-editor__remove"
                        onClick={() => removeSocialLink(index)}
                        type="button"
                      >
                        <Trash2 size={16} strokeWidth={1.8} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                  {form.socialLinks.length === 0 ? (
                    <p className="empty-state">还没有社交入口。</p>
                  ) : null}
                </div>
              </div>
            ) : null}
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
            <div className="musing-list settings-musings">
              {form.musings.slice(0, 2).map((musing, index) => (
                <div className="musing-item" key={`${musing.content}-${index}`}>
                  <p>{musing.content}</p>
                  <small>{musing.date}</small>
                </div>
              ))}
            </div>
          </div>
          <div className="admin-note-list">
            {form.socialLinks.map((link) => (
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
        socialLinks: nextForm.socialLinks.filter((_, itemIndex) => itemIndex !== index),
      }
    })
  }
}

function settingToForm(value: Record<string, unknown>): SiteSettingForm {
  return {
    title: stringValue(value.title, initialForm.title),
    owner: stringValue(value.owner, initialForm.owner),
    avatarUrl: stringValue(value.avatar_url, initialForm.avatarUrl),
    description: stringValue(value.description, initialForm.description),
    quote: stringValue(value.quote, initialForm.quote),
    musings: musingsValue(value.musings),
    socialLinks: socialLinksValue(value.social_links),
  }
}

function formToSettingValue(form: SiteSettingForm): Record<string, unknown> {
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

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback
}

function musingsValue(value: unknown): SiteMusing[] {
  if (!Array.isArray(value)) {
    return initialForm.musings
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
    return initialForm.socialLinks
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

  return socialLinks.length > 0 ? socialLinks : initialForm.socialLinks
}
