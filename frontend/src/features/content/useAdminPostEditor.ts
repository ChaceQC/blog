import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { invalidatePostCaches } from '../../app/queryInvalidation.ts'
import { usePagedItems } from '../../hooks/usePagedItems.ts'
import { hasAdminPermission } from '../auth/permissions.ts'
import {
  createAdminPost,
  deleteAdminPost,
  listAdminPosts,
  previewAdminPost,
  publishAdminPost,
  updateAdminPost,
} from './api.ts'
import {
  createEmptyPostForm,
  formatPostSaveError,
  normalizePostForm,
  postToForm,
  postToPreviewInput,
  slugPattern,
} from './postForm.ts'

import type { AuthSession } from '../auth/session.ts'
import type {
  AdminPostItem,
  AdminPostListResponse,
  ContentStatus,
  PostFormPayload,
} from './types.ts'

const emptyPosts: AdminPostItem[] = []
const LIST_PAGE_SIZE = 8

export function useAdminPostEditor(session: AuthSession | null) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | 'new'>('new')
  const [form, setForm] = useState<PostFormPayload | null>(null)
  const [previewInput, setPreviewInput] = useState<{
    content_md: string
    slug: string
  } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const [isPreviewOpen, setPreviewOpen] = useState(false)

  const postsQuery = useQuery({
    queryKey: ['admin-posts'],
    queryFn: listAdminPosts,
  })
  const posts = postsQuery.data?.items ?? emptyPosts
  const { safePage: safeListPage, visibleItems: visiblePosts } = usePagedItems(
    posts,
    listPage,
    LIST_PAGE_SIZE,
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
    savedForm === null ||
    postFormSignature(currentForm) !== postFormSignature(savedForm)
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

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedPost || !canWrite) {
        throw new Error('当前文章无法删除')
      }
      return deleteAdminPost(selectedPost.id, session.csrfToken)
    },
    onSuccess: (post) => {
      queryClient.setQueryData<AdminPostListResponse>(
        ['admin-posts'],
        (current) => removePostListItem(current, post.id),
      )
      void invalidatePostCaches(queryClient)
      startNewPost()
      setNotice('文章已删除')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '删除失败')
    },
  })

  function selectPost(post: AdminPostItem) {
    setSelectedId(post.id)
    setForm(postToForm(post))
    setPreviewInput(postToPreviewInput(post))
    setPreviewOpen(false)
    setNotice(null)
  }

  function startNewPost() {
    setSelectedId('new')
    setForm(null)
    setPreviewInput(null)
    setPreviewOpen(false)
    setNotice(null)
  }

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

  function openPostPreview() {
    if (canPreview) {
      setPreviewInput({
        slug: currentForm.slug.trim(),
        content_md: currentForm.content_md,
      })
    }
    setPreviewOpen(true)
  }

  return {
    canPreview,
    canSaveDraft,
    canSubmitPublish,
    canWrite,
    currentForm,
    isError: postsQuery.isError,
    isLoading: postsQuery.isLoading,
    isPreviewOpen,
    listPageSize: LIST_PAGE_SIZE,
    notice,
    openPostPreview,
    posts,
    previewHtml,
    previewQuery,
    deleteMutation,
    publishMutation,
    safeListPage,
    saveAsDraft,
    saveMutation,
    selectedPost,
    selectPost,
    setListPage,
    setPreviewOpen,
    startNewPost,
    updateForm,
    updateStatus,
    visiblePosts,
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

function removePostListItem(
  current: AdminPostListResponse | undefined,
  postId: number,
): AdminPostListResponse {
  if (!current) {
    return { items: [] }
  }
  return {
    ...current,
    items: current.items.filter((item) => item.id !== postId),
  }
}
