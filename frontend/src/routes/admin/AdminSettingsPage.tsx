import { Save, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'

import { siteSettings } from '../../features/settings/siteSettings.ts'

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
  const [form, setForm] = useState(initialForm)

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>SETTINGS</span>
        <h1>站点设置</h1>
        <button className="text-button admin-heading__action" disabled type="button">
          <Save size={17} strokeWidth={1.8} aria-hidden="true" />
          保存设置
        </button>
      </section>

      <div className="admin-workspace admin-workspace--two">
        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>公开站点</span>
            <small>site profile</small>
          </div>
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

      <section className="admin-panel">
        <div className="section-heading">
          <span>生产边界</span>
          <small>
            <ShieldCheck size={14} strokeWidth={1.8} aria-hidden="true" />
            基线
          </small>
        </div>
        <div className="settings-grid">
          <span>
            <strong>后台 Cookie</strong>
            <small>HttpOnly + CSRF 双提交</small>
          </span>
          <span>
            <strong>内容传输</strong>
            <small>sensitive-v1 / content-v1 加密信封</small>
          </span>
          <span>
            <strong>公网入口</strong>
            <small>Nginx 只暴露 80/443</small>
          </span>
        </div>
      </section>
    </div>
  )

  function updateForm<Key extends keyof SiteSettingForm>(
    key: Key,
    value: SiteSettingForm[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }))
  }
}
