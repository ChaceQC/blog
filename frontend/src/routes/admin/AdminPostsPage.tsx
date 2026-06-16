import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brackets, Eye, FilePlus2, Link2, Rocket, Save } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { MathHtml } from '../../components/MathHtml.tsx'
import {
  createAdminPost,
  listAdminPosts,
  previewAdminPost,
  publishAdminPost,
  updateAdminPost,
} from '../../features/content/api.ts'
import {
  contentStatusLabels,
  postVisibilityLabels,
} from '../../features/content/contentLabels.ts'
import { hasAdminPermission } from '../../features/auth/permissions.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type {
  AdminPostItem,
  ContentStatus,
  PostFormPayload,
  PostVisibility,
} from '../../features/content/types.ts'

const emptyPostForm: PostFormPayload = {
  title: '',
  slug: '',
  summary: '',
  content_md: '',
  status: 'draft',
  visibility: 'public',
  seo_title: '',
  seo_description: '',
}
const emptyPosts: AdminPostItem[] = []
const slugPattern = /^[a-z0-9][a-z0-9_-]*$/

export function AdminPostsPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const markdownRef = useRef<HTMLTextAreaElement>(null)
  const [selectedId, setSelectedId] = useState<number | 'new'>('new')
  const [form, setForm] = useState<PostFormPayload>(emptyPostForm)
  const [previewInput, setPreviewInput] = useState<{
    content_md: string
    slug: string
  } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-posts'],
    queryFn: listAdminPosts,
  })
  const posts = data?.items ?? emptyPosts
  const selectedPost = useMemo(
    () => posts.find((post) => post.id === selectedId) ?? null,
    [posts, selectedId],
  )
  const canWrite =
    session !== null && hasAdminPermission(session.user, 'post:write')
  const canPublish =
    session !== null && hasAdminPermission(session.user, 'post:publish')
  const canPreview =
    session !== null &&
    canWrite &&
    slugPattern.test(form.slug.trim()) &&
    form.content_md.trim().length > 0
  const previewQuery = useQuery({
    queryKey: [
      'admin-post-preview',
      previewInput?.slug,
      previewInput?.content_md,
    ],
    queryFn: () => {
      if (!session || !previewInput) {
        throw new Error('预览参数不足')
      }
      return previewAdminPost(previewInput, session.csrfToken)
    },
    enabled: session !== null && canWrite && canPreview && previewInput !== null,
    staleTime: 10_000,
  })
  const previewHtml =
    (canPreview ? previewQuery.data?.content_html : null) ??
    (!canPreview ? selectedPost?.content_html : null) ??
    ''

  useEffect(() => {
    if (!canPreview) {
      return
    }

    const timer = window.setTimeout(() => {
      setPreviewInput({
        slug: form.slug.trim(),
        content_md: form.content_md,
      })
    }, 350)
    return () => window.clearTimeout(timer)
  }, [canPreview, form.content_md, form.slug])

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session || !canWrite) {
        throw new Error('当前账号没有文章写入权限')
      }

      const payload = normalizePostForm(form)
      if (selectedPost) {
        return updateAdminPost(selectedPost.id, payload, session.csrfToken)
      }
      return createAdminPost(payload, session.csrfToken)
    },
    onSuccess: (post) => {
      queryClient.invalidateQueries({ queryKey: ['admin-posts'] })
      setSelectedId(post.id)
      setForm(postToForm(post))
      setNotice('文章已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })
  const publishMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedPost || !canPublish) {
        throw new Error('当前文章无法发布')
      }
      return publishAdminPost(selectedPost.id, session.csrfToken)
    },
    onSuccess: (post) => {
      queryClient.invalidateQueries({ queryKey: ['admin-posts'] })
      setSelectedId(post.id)
      setForm(postToForm(post))
      setNotice('文章已发布')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '发布失败')
    },
  })

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>写作</span>
        <h1>文章管理</h1>
        <button
          className="text-button admin-heading__action"
          onClick={() => {
            setSelectedId('new')
            setForm(emptyPostForm)
            setNotice(null)
          }}
          type="button"
        >
          <FilePlus2 size={17} strokeWidth={1.8} aria-hidden="true" />
          新建文章
        </button>
      </section>

      <div className="admin-workspace">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>文章列表</span>
            <small>{isLoading ? '加载中' : `共 ${posts.length} 篇`}</small>
          </div>
          {isError ? (
            <p className="form-error">文章列表加载失败</p>
          ) : (
            <div className="content-list">
              {posts.map((post) => (
                <button
                  className={post.id === selectedId ? 'content-row active' : 'content-row'}
                  key={post.id}
                  onClick={() => {
                    setSelectedId(post.id)
                    setForm(postToForm(post))
                    setNotice(null)
                  }}
                  type="button"
                >
                  <span>
                    <strong>{post.title}</strong>
                    <small>/{post.slug}</small>
                  </span>
                  <small>{contentStatusLabels[post.status]}</small>
                </button>
              ))}
              {posts.length === 0 && !isLoading ? (
                <p className="empty-state">还没有文章，先创建第一篇草稿。</p>
              ) : null}
            </div>
          )}
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>{selectedPost ? '编辑文章' : '新建文章'}</span>
            <small>{notice ?? '草稿会按当前内容保存'}</small>
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
                可见性
                <select
                  value={form.visibility}
                  onChange={(event) =>
                    updateForm('visibility', event.target.value as PostVisibility)
                  }
                >
                  {Object.entries(postVisibilityLabels).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                SEO 标题
                <input
                  value={form.seo_title ?? ''}
                  onChange={(event) => updateForm('seo_title', event.target.value)}
                />
              </label>
            </div>
            <label>
              摘要
              <textarea
                value={form.summary ?? ''}
                onChange={(event) => updateForm('summary', event.target.value)}
                rows={3}
              />
            </label>
            <div className="field-group">
              <span className="field-label">Markdown 正文</span>
              <div className="markdown-tools">
                <button
                  className="text-button text-button--muted"
                  onClick={() => wrapMarkdownSelection('[', '](https://)', '链接文字')}
                  type="button"
                >
                  <Link2 size={16} strokeWidth={1.8} aria-hidden="true" />
                  链接
                </button>
                <button
                  className="text-button text-button--muted"
                  onClick={() => wrapMarkdownSelection('![', ']()', '图片说明')}
                  type="button"
                >
                  <Brackets size={16} strokeWidth={1.8} aria-hidden="true" />
                  图片语法
                </button>
              </div>
              <textarea
                aria-label="Markdown 正文"
                ref={markdownRef}
                value={form.content_md}
                onChange={(event) => updateForm('content_md', event.target.value)}
                rows={12}
                required
              />
            </div>
            <label>
              SEO 描述
              <textarea
                value={form.seo_description ?? ''}
                onChange={(event) => updateForm('seo_description', event.target.value)}
                rows={2}
              />
            </label>
            <div className="form-actions">
              <button
                className="text-button"
                disabled={!canWrite || saveMutation.isPending}
                type="submit"
              >
                <Save size={17} strokeWidth={1.8} aria-hidden="true" />
                {saveMutation.isPending ? '保存中' : '保存'}
              </button>
              <button
                className="text-button text-button--muted"
                disabled={!selectedPost || !canPublish || publishMutation.isPending}
                onClick={() => publishMutation.mutate()}
                type="button"
              >
                <Rocket size={17} strokeWidth={1.8} aria-hidden="true" />
                {publishMutation.isPending ? '发布中' : '发布'}
              </button>
            </div>
          </form>
        </section>

        <section className="admin-panel admin-panel--preview">
          <div className="section-heading">
            <span>文章预览</span>
            <small>
              <Eye size={14} strokeWidth={1.8} aria-hidden="true" />
              {previewQuery.isFetching ? '正在更新' : '实时预览'}
            </small>
          </div>
          {previewHtml ? (
            <MathHtml
              className="content-preview"
              html={previewHtml}
            />
          ) : (
            <p className="empty-state">填写 Slug 和正文后显示预览。</p>
          )}
          {previewQuery.isError ? (
            <p className="form-error">预览暂时无法更新</p>
          ) : null}
        </section>
      </div>
    </div>
  )

  function updateForm<Key extends keyof PostFormPayload>(
    key: Key,
    value: PostFormPayload[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function wrapMarkdownSelection(prefix: string, suffix: string, fallback: string) {
    const textarea = markdownRef.current
    const start = textarea?.selectionStart ?? form.content_md.length
    const end = textarea?.selectionEnd ?? form.content_md.length
    const selectedText = form.content_md.slice(start, end) || fallback
    const snippet = `${prefix}${selectedText}${suffix}`
    const nextContent = `${form.content_md.slice(0, start)}${snippet}${form.content_md.slice(end)}`
    updateForm('content_md', nextContent)
    window.requestAnimationFrame(() => {
      markdownRef.current?.focus()
      const cursor = start + snippet.length
      markdownRef.current?.setSelectionRange(
        cursor,
        cursor,
      )
    })
  }
}

function postToForm(post: AdminPostItem): PostFormPayload {
  return {
    title: post.title,
    slug: post.slug,
    summary: post.summary ?? '',
    content_md: post.content_md,
    status: post.status,
    visibility: post.visibility,
    seo_title: post.seo_title ?? '',
    seo_description: post.seo_description ?? '',
  }
}

function normalizePostForm(form: PostFormPayload): PostFormPayload {
  return {
    ...form,
    summary: nullableText(form.summary),
    seo_title: nullableText(form.seo_title),
    seo_description: nullableText(form.seo_description),
  }
}

function nullableText(value: string | null): string | null {
  const trimmed = value?.trim() ?? ''
  return trimmed === '' ? null : trimmed
}
