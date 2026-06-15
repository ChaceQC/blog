import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, FilePlus2, Rocket, Save } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  createAdminPost,
  listAdminPosts,
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

export function AdminPostsPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | 'new'>('new')
  const [form, setForm] = useState<PostFormPayload>(emptyPostForm)
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
        <span>POSTS</span>
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
            <small>{notice ?? 'content-v1 加密保存'}</small>
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
            <label>
              Markdown 正文
              <textarea
                value={form.content_md}
                onChange={(event) => updateForm('content_md', event.target.value)}
                rows={12}
                required
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
            <span>HTML 预览</span>
            <small>
              <Eye size={14} strokeWidth={1.8} aria-hidden="true" />
              后端 sanitize
            </small>
          </div>
          {selectedPost ? (
            <article
              className="content-preview"
              dangerouslySetInnerHTML={{ __html: selectedPost.content_html }}
            />
          ) : (
            <p className="empty-state">保存后可查看后端渲染结果。</p>
          )}
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
