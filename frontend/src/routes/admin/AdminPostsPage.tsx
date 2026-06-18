import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brackets, Eye, FilePlus2, Link2, Rocket, Save } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { AdminModal } from '../../components/AdminModal.tsx'
import { MathHtml } from '../../components/MathHtml.tsx'
import { invalidatePostCaches } from '../../app/queryInvalidation.ts'
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
import { PostCoverPicker } from '../../features/content/PostCoverPicker.tsx'
import {
  createEmptyPostForm,
  formatPostSaveError,
  inputToLabels,
  labelsToInput,
  normalizePostForm,
  postToForm,
  postToPreviewInput,
  slugPattern,
} from '../../features/content/postForm.ts'
import { hasAdminPermission } from '../../features/auth/permissions.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type {
  AdminPostListResponse,
  AdminPostItem,
  ContentStatus,
  PostFormPayload,
  PostVisibility,
} from '../../features/content/types.ts'

const emptyPosts: AdminPostItem[] = []
const LIST_PAGE_SIZE = 8

export function AdminPostsPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const markdownRef = useRef<HTMLTextAreaElement>(null)
  const [selectedId, setSelectedId] = useState<number | 'new'>('new')
  const [form, setForm] = useState<PostFormPayload | null>(null)
  const [previewInput, setPreviewInput] = useState<{
    content_md: string
    slug: string
  } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const [isPreviewOpen, setPreviewOpen] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-posts'],
    queryFn: listAdminPosts,
  })
  const posts = data?.items ?? emptyPosts
  const safeListPage = Math.min(
    listPage,
    Math.max(0, Math.ceil(posts.length / LIST_PAGE_SIZE) - 1),
  )
  const visiblePosts = posts.slice(
    safeListPage * LIST_PAGE_SIZE,
    safeListPage * LIST_PAGE_SIZE + LIST_PAGE_SIZE,
  )
  const selectedPost = useMemo(
    () => posts.find((post) => post.id === selectedId) ?? null,
    [posts, selectedId],
  )
  const currentForm = form ?? createEmptyPostForm(posts)
  const savedForm = useMemo(
    () => (selectedPost ? postToForm(selectedPost) : null),
    [selectedPost],
  )
  const canWrite =
    session !== null && hasAdminPermission(session.user, 'post:write')
  const canPublish =
    session !== null && hasAdminPermission(session.user, 'post:publish')
  const hasUnsavedChanges =
    savedForm === null || postFormSignature(currentForm) !== postFormSignature(savedForm)
  const canSaveDraft = canWrite && (selectedPost === null || hasUnsavedChanges)
  const isPublishStatusLocked =
    currentForm.status === 'published' || currentForm.status === 'scheduled'
  const canSubmitPublish =
    selectedPost !== null && canPublish && !hasUnsavedChanges && !isPublishStatusLocked
  const canPreview =
    session !== null &&
    canWrite &&
    slugPattern.test(currentForm.slug.trim()) &&
    currentForm.content_md.trim().length > 0
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
    enabled:
      isPreviewOpen &&
      session !== null &&
      canWrite &&
      canPreview &&
      previewInput !== null,
    staleTime: 10_000,
  })
  const previewHtml =
    (canPreview ? previewQuery.data?.content_html : null) ??
    (!canPreview ? selectedPost?.content_html : null) ??
    ''

  useEffect(() => {
    if (!isPreviewOpen || !canPreview) {
      return
    }

    const timer = window.setTimeout(() => {
      setPreviewInput({
        slug: currentForm.slug.trim(),
        content_md: currentForm.content_md,
      })
    }, 350)
    return () => window.clearTimeout(timer)
  }, [canPreview, currentForm.content_md, currentForm.slug, isPreviewOpen])

  const saveMutation = useMutation({
    mutationFn: async (draftForm: PostFormPayload) => {
      if (!session || !canWrite) {
        throw new Error('当前账号没有文章写入权限')
      }

      const payload = normalizePostForm(draftForm)
      if (selectedPost) {
        return updateAdminPost(selectedPost.id, payload, session.csrfToken)
      }
      return createAdminPost(payload, session.csrfToken)
    },
    onSuccess: (post) => {
      queryClient.setQueryData<AdminPostListResponse>(
        ['admin-posts'],
        (current) => upsertPostListItem(current, post),
      )
      void invalidatePostCaches(queryClient)
      setSelectedId(post.id)
      setForm(postToForm(post))
      setPreviewInput(postToPreviewInput(post))
      setNotice('草稿已保存')
    },
    onError: (error) => {
      setNotice(formatPostSaveError(error))
    },
  })
  const publishMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedPost || !canSubmitPublish) {
        throw new Error('当前文章无法发布')
      }
      return publishAdminPost(selectedPost.id, session.csrfToken)
    },
    onSuccess: (post) => {
      void invalidatePostCaches(queryClient)
      setSelectedId(post.id)
      setForm(postToForm(post))
      setPreviewInput(postToPreviewInput(post))
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
            setForm(null)
            setPreviewInput(null)
            setPreviewOpen(false)
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
              {visiblePosts.map((post) => (
                <button
                  className={post.id === selectedId ? 'content-row active' : 'content-row'}
                  key={post.id}
                  onClick={() => {
                    setSelectedId(post.id)
                    setForm(postToForm(post))
                    setPreviewInput(postToPreviewInput(post))
                    setPreviewOpen(false)
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
          <ListPager
            page={safeListPage}
            pageSize={LIST_PAGE_SIZE}
            totalItems={posts.length}
            isLoading={isLoading}
            variant="admin"
            onPageChange={setListPage}
          />
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>{selectedPost ? '编辑文章' : '新建文章'}</span>
            <small>{notice ?? '草稿会按当前内容保存'}</small>
          </div>
          <form className="content-form" onSubmit={(event) => {
            event.preventDefault()
            saveAsDraft()
          }}>
            <div className="form-grid form-grid--two">
              <label>
                标题
                <input
                  value={currentForm.title}
                  onChange={(event) => updateForm('title', event.target.value)}
                  required
                />
              </label>
              <label>
                Slug
                <input
                  value={currentForm.slug}
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
                  value={currentForm.status}
                  onChange={(event) => updateStatus(event.target.value as ContentStatus)}
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
                  value={currentForm.visibility}
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
                  value={currentForm.seo_title ?? ''}
                  onChange={(event) => updateForm('seo_title', event.target.value)}
                />
              </label>
            </div>
            <div className="form-grid form-grid--three">
              {currentForm.status === 'scheduled' ? (
                <label>
                  定时发布时间
                  <input
                    type="datetime-local"
                    value={currentForm.published_at ?? ''}
                    onChange={(event) =>
                      updateForm('published_at', event.target.value || null)
                    }
                  />
                </label>
              ) : null}
              <label>
                分类
                <input
                  placeholder="随笔，技术"
                  value={labelsToInput(currentForm.category_names)}
                  onChange={(event) =>
                    updateForm('category_names', inputToLabels(event.target.value))
                  }
                />
              </label>
              <label>
                标签
                <input
                  placeholder="React，FastAPI，生活"
                  value={labelsToInput(currentForm.tag_names)}
                  onChange={(event) =>
                    updateForm('tag_names', inputToLabels(event.target.value))
                  }
                />
              </label>
            </div>
            <PostCoverPicker
              disabled={!canWrite}
              value={currentForm.cover_file_id}
              onChange={(value) => updateForm('cover_file_id', value)}
            />
            <label>
              摘要
              <textarea
                value={currentForm.summary ?? ''}
                onChange={(event) => updateForm('summary', event.target.value)}
                rows={3}
              />
            </label>
            <div className="field-group">
              <span className="field-label">Markdown 正文</span>
              <div className="markdown-toolbar">
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
                <button
                  aria-label="预览文章"
                  className="icon-button admin-preview-trigger"
                  disabled={!canPreview && !selectedPost?.content_html}
                  onClick={openPostPreview}
                  title="预览"
                  type="button"
                >
                  <Eye size={17} strokeWidth={1.8} aria-hidden="true" />
                </button>
              </div>
              <textarea
                aria-label="Markdown 正文"
                ref={markdownRef}
                value={currentForm.content_md}
                onChange={(event) => updateForm('content_md', event.target.value)}
                rows={12}
                required
              />
            </div>
            <label>
              SEO 描述
              <textarea
                value={currentForm.seo_description ?? ''}
                onChange={(event) => updateForm('seo_description', event.target.value)}
                rows={2}
              />
            </label>
            <label>
              SEO 关键词
              <input
                value={currentForm.seo_keywords ?? ''}
                onChange={(event) => updateForm('seo_keywords', event.target.value)}
                placeholder="多个关键词用逗号分隔"
              />
            </label>
            <div className="form-actions">
              <button
                className="text-button"
                disabled={!canSaveDraft || saveMutation.isPending}
                type="submit"
              >
                <Save size={17} strokeWidth={1.8} aria-hidden="true" />
                {saveMutation.isPending ? '保存中' : '保存'}
              </button>
              <button
                className="text-button text-button--muted"
                disabled={!canSubmitPublish || publishMutation.isPending}
                onClick={() => publishMutation.mutate()}
                type="button"
              >
                <Rocket size={17} strokeWidth={1.8} aria-hidden="true" />
                {publishMutation.isPending ? '发布中' : '发布'}
              </button>
            </div>
          </form>
        </section>
      </div>
      <AdminModal
        className="admin-modal--wide"
        description={previewQuery.isFetching ? '正在更新' : '当前渲染结果'}
        isOpen={isPreviewOpen}
        onClose={() => setPreviewOpen(false)}
        title="文章预览"
      >
        {previewHtml ? (
          <MathHtml
            className="content-preview content-preview--modal"
            html={previewHtml}
          />
        ) : (
          <p className="empty-state">填写 Slug 和正文后显示预览。</p>
        )}
        {previewQuery.isError ? (
          <p className="form-error">预览暂时无法更新</p>
        ) : null}
      </AdminModal>
    </div>
  )

  function updateForm<Key extends keyof PostFormPayload>(
    key: Key,
    value: PostFormPayload[Key],
  ) {
    setForm((current) => ({ ...(current ?? currentForm), [key]: value }))
  }

  function updateStatus(status: ContentStatus) {
    setForm((current) => {
      const nextForm = { ...(current ?? currentForm), status }
      if (status !== 'scheduled') {
        nextForm.published_at = null
      }
      return nextForm
    })
  }

  function saveAsDraft() {
    if (!canSaveDraft || saveMutation.isPending) {
      return
    }
    const draftForm: PostFormPayload = {
      ...currentForm,
      status: 'draft',
      published_at: null,
    }
    setForm(draftForm)
    saveMutation.mutate(draftForm)
  }

  function wrapMarkdownSelection(prefix: string, suffix: string, fallback: string) {
    const textarea = markdownRef.current
    const start = textarea?.selectionStart ?? currentForm.content_md.length
    const end = textarea?.selectionEnd ?? currentForm.content_md.length
    const selectedText = currentForm.content_md.slice(start, end) || fallback
    const snippet = `${prefix}${selectedText}${suffix}`
    const nextContent = `${currentForm.content_md.slice(0, start)}${snippet}${currentForm.content_md.slice(end)}`
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

  function openPostPreview() {
    if (canPreview) {
      setPreviewInput({
        slug: currentForm.slug.trim(),
        content_md: currentForm.content_md,
      })
    }
    setPreviewOpen(true)
  }
}

function postFormSignature(form: PostFormPayload): string {
  return JSON.stringify({
    ...form,
    category_names: [...form.category_names],
    tag_names: [...form.tag_names],
  })
}

function upsertPostListItem(
  current: AdminPostListResponse | undefined,
  post: AdminPostItem,
): AdminPostListResponse {
  if (!current) {
    return { items: [post] }
  }
  const existingIndex = current.items.findIndex((item) => item.id === post.id)
  if (existingIndex === -1) {
    return { ...current, items: [post, ...current.items] }
  }
  return {
    ...current,
    items: current.items.map((item) => (item.id === post.id ? post : item)),
  }
}
