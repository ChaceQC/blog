import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, FilePlus2, Save } from 'lucide-react'
import { useMemo, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { MathHtml } from '../../components/MathHtml.tsx'
import { invalidatePageCaches } from '../../app/queryInvalidation.ts'
import {
  createAdminPage,
  listAdminPages,
  updateAdminPage,
} from '../../features/content/api.ts'
import { contentStatusLabels } from '../../features/content/contentLabels.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type {
  AdminPageItem,
  ContentStatus,
  PageFormPayload,
} from '../../features/content/types.ts'

const emptyPageForm: PageFormPayload = {
  title: '',
  slug: '',
  content_md: '',
  status: 'draft',
  show_in_nav: false,
  sort_order: 0,
  seo_title: '',
  seo_description: '',
}
const emptyPages: AdminPageItem[] = []
const LIST_PAGE_SIZE = 8

export function AdminPagesPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | 'new'>('new')
  const [form, setForm] = useState<PageFormPayload>(emptyPageForm)
  const [notice, setNotice] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-pages'],
    queryFn: listAdminPages,
  })
  const pages = data?.items ?? emptyPages
  const [listPage, setListPage] = useState(0)
  const safeListPage = Math.min(
    listPage,
    Math.max(0, Math.ceil(pages.length / LIST_PAGE_SIZE) - 1),
  )
  const visiblePages = pages.slice(
    safeListPage * LIST_PAGE_SIZE,
    safeListPage * LIST_PAGE_SIZE + LIST_PAGE_SIZE,
  )
  const selectedPage = useMemo(
    () => pages.find((page) => page.id === selectedId) ?? null,
    [pages, selectedId],
  )

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }

      const payload = normalizePageForm(form)
      if (selectedPage) {
        return updateAdminPage(selectedPage.id, payload, session.csrfToken)
      }
      return createAdminPage(payload, session.csrfToken)
    },
    onSuccess: (page) => {
      void invalidatePageCaches(queryClient)
      setSelectedId(page.id)
      setForm(pageToForm(page))
      setNotice('页面已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>页面</span>
        <h1>页面管理</h1>
        <button
          className="text-button admin-heading__action"
          onClick={() => {
            setSelectedId('new')
            setForm(emptyPageForm)
            setNotice(null)
          }}
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
                  className={page.id === selectedId ? 'content-row active' : 'content-row'}
                  key={page.id}
                  onClick={() => {
                    setSelectedId(page.id)
                    setForm(pageToForm(page))
                    setNotice(null)
                  }}
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
            pageSize={LIST_PAGE_SIZE}
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
            <label>
              Markdown 正文
              <textarea
                value={form.content_md}
                onChange={(event) => updateForm('content_md', event.target.value)}
                rows={14}
                required
              />
            </label>
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
            </div>
          </form>
        </section>

        <section className="admin-panel admin-panel--preview">
          <div className="section-heading">
            <span>页面预览</span>
            <small>
              <Eye size={14} strokeWidth={1.8} aria-hidden="true" />
              保存后的样子
            </small>
          </div>
          {selectedPage ? (
            <MathHtml
              className="content-preview"
              html={selectedPage.content_html}
            />
          ) : (
            <p className="empty-state">保存后可查看后端渲染结果。</p>
          )}
        </section>
      </div>
    </div>
  )

  function updateForm<Key extends keyof PageFormPayload>(
    key: Key,
    value: PageFormPayload[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }))
  }
}

function pageToForm(page: AdminPageItem): PageFormPayload {
  return {
    title: page.title,
    slug: page.slug,
    content_md: page.content_md,
    status: page.status,
    show_in_nav: page.show_in_nav,
    sort_order: page.sort_order,
    seo_title: page.seo_title ?? '',
    seo_description: page.seo_description ?? '',
  }
}

function normalizePageForm(form: PageFormPayload): PageFormPayload {
  return {
    ...form,
    seo_title: nullableText(form.seo_title),
    seo_description: nullableText(form.seo_description),
  }
}

function nullableText(value: string | null): string | null {
  const trimmed = value?.trim() ?? ''
  return trimmed === '' ? null : trimmed
}
