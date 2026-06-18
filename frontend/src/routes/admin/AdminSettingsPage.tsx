import { Plus, Save, SlidersHorizontal, Trash2 } from 'lucide-react'

import {
  settingSectionLabels,
  useAdminSiteProfileEditor,
} from '../../features/settings/useAdminSiteProfileEditor.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type { SettingSection } from '../../features/settings/useAdminSiteProfileEditor.ts'

export function AdminSettingsPage() {
  const { session } = useAuth()
  const editor = useAdminSiteProfileEditor(session)
  const {
    activeSection,
    addSocialLink,
    form,
    isError,
    isLoading,
    notice,
    removeSocialLink,
    saveMutation,
    setActiveSection,
    updateForm,
    updateMusing,
    updateSocialLink,
  } = editor

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
}
