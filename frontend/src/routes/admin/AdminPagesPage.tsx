import { Eye, FilePlus2, Save, Trash2 } from 'lucide-react'

import { ListPager } from '../../components/ListPager.tsx'
import { AdminModal } from '../../components/AdminModal.tsx'
import { MathHtml } from '../../components/MathHtml.tsx'
import { contentStatusLabels } from '../../features/content/contentLabels.ts'
import { useAdminPageEditor } from '../../features/content/useAdminPageEditor.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type { ContentStatus } from '../../features/content/types.ts'

export function AdminPagesPage() {
  const { session } = useAuth()
  const editor = useAdminPageEditor(session)
  const {
    form,
    isError,
    isLoading,
    isPreviewOpen,
    listPageSize,
    notice,
    pages,
    safeListPage,
    deleteMutation,
    saveMutation,
    selectedPage,
    setListPage,
    setPreviewOpen,
    startNewPage,
    updateForm,
    visiblePages,
    selectPage,
  } = editor

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>页面</span>
        <h1>页面管理</h1>
        <button
          className="text-button admin-heading__action"
          onClick={startNewPage}
          type="button"
        >
          <FilePlus2 size={17} strokeWidth={1.8} aria-hidden="true" />
          新建页面
        </button>
      </section>

      <div className="admin-workspace">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>页面列表</span>
            <small>{isLoading ? '加载中' : `共 ${pages.length} 页`}</small>
          </div>
          {isError ? (
            <p className="form-error">页面列表加载失败</p>
          ) : (
            <div className="content-list">
              {visiblePages.map((page) => (
                <button
                  className={
                    page.id === selectedPage?.id ? 'content-row active' : 'content-row'
                  }
                  key={page.id}
                  onClick={() => selectPage(page)}
                  type="button"
                >
                  <span>
                    <strong>{page.title}</strong>
                    <small>/{page.slug}</small>
                  </span>
                  <small>{page.show_in_nav ? '导航显示' : contentStatusLabels[page.status]}</small>
                </button>
              ))}
              {pages.length === 0 && !isLoading ? (
                <p className="empty-state">还没有独立页面。</p>
              ) : null}
            </div>
          )}
          <ListPager
            page={safeListPage}
            pageSize={listPageSize}
            totalItems={pages.length}
            isLoading={isLoading}
            variant="admin"
            onPageChange={setListPage}
          />
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>{selectedPage ? '编辑页面' : '新建页面'}</span>
            <small>{notice ?? '保存后会更新预览'}</small>
          </div>
          <form className="content-form" onSubmit={(event) => {
            event.preventDefault()
            saveMutation.mutate()
          }}>
            <div className="form-grid form-grid--two">
              <label>
                标题
                <input
                  value={form.title}
                  onChange={(event) => updateForm('title', event.target.value)}
                  required
                />
              </label>
              <label>
                Slug
                <input
                  value={form.slug}
                  onChange={(event) => updateForm('slug', event.target.value)}
                  pattern="[a-z0-9][a-z0-9_\-]*"
                  required
                />
              </label>
            </div>
            <div className="form-grid form-grid--three">
              <label>
                状态
                <select
                  value={form.status}
                  onChange={(event) =>
                    updateForm('status', event.target.value as ContentStatus)
                  }
                >
                  {Object.entries(contentStatusLabels).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                排序
                <input
                  min={0}
                  max={10000}
                  type="number"
                  value={form.sort_order}
                  onChange={(event) =>
                    updateForm('sort_order', Number(event.target.value))
                  }
                />
              </label>
              <label className="checkbox-field">
                <input
                  checked={form.show_in_nav}
                  onChange={(event) => updateForm('show_in_nav', event.target.checked)}
                  type="checkbox"
                />
                显示在导航
              </label>
            </div>
            <div className="field-group">
              <span className="field-label">Markdown 正文</span>
              <div className="markdown-toolbar markdown-toolbar--end">
                <button
                  aria-label="预览页面"
                  className="icon-button admin-preview-trigger"
                  disabled={!selectedPage?.content_html}
                  onClick={() => setPreviewOpen(true)}
                  title="预览"
                  type="button"
                >
                  <Eye size={17} strokeWidth={1.8} aria-hidden="true" />
                </button>
              </div>
              <textarea
                aria-label="Markdown 正文"
                value={form.content_md}
                onChange={(event) => updateForm('content_md', event.target.value)}
                rows={14}
                required
              />
            </div>
            <div className="form-grid form-grid--two">
              <label>
                SEO 标题
                <input
                  value={form.seo_title ?? ''}
                  onChange={(event) => updateForm('seo_title', event.target.value)}
                />
              </label>
              <label>
                SEO 描述
                <textarea
                  value={form.seo_description ?? ''}
                  onChange={(event) => updateForm('seo_description', event.target.value)}
                  rows={2}
                />
              </label>
            </div>
            <div className="form-actions">
              <button
                className="text-button"
                disabled={saveMutation.isPending}
                type="submit"
              >
                <Save size={17} strokeWidth={1.8} aria-hidden="true" />
                {saveMutation.isPending ? '保存中' : '保存'}
              </button>
              <button
                className="text-button text-button--danger"
                disabled={!selectedPage || deleteMutation.isPending}
                onClick={() => {
                  if (window.confirm('确定删除这个页面吗？')) {
                    deleteMutation.mutate()
                  }
                }}
                type="button"
              >
                <Trash2 size={17} strokeWidth={1.8} aria-hidden="true" />
                {deleteMutation.isPending ? '删除中' : '删除'}
              </button>
            </div>
          </form>
        </section>
      </div>
      <AdminModal
        className="admin-modal--wide"
        description="保存后的渲染结果"
        isOpen={isPreviewOpen}
        onClose={() => setPreviewOpen(false)}
        title="页面预览"
      >
        {selectedPage ? (
          <MathHtml
            className="content-preview content-preview--modal"
            html={selectedPage.content_html}
          />
        ) : (
          <p className="empty-state">保存后可查看后端渲染结果。</p>
        )}
      </AdminModal>
    </div>
  )

}
