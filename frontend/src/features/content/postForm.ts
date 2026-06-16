import type { AdminPostItem, PostFormPayload, PostWritePayload } from './types.ts'

export const emptyPostForm: PostFormPayload = {
  title: '',
  slug: '',
  summary: '',
  content_md: '',
  status: 'draft',
  visibility: 'public',
  cover_file_id: null,
  seo_title: '',
  seo_description: '',
}

export const slugPattern = /^[a-z0-9][a-z0-9_-]*$/

export function createEmptyPostForm(posts: AdminPostItem[]): PostFormPayload {
  return {
    ...emptyPostForm,
    slug: nextPostSlug(posts),
  }
}

export function postToForm(post: AdminPostItem): PostFormPayload {
  return {
    title: post.title,
    slug: post.slug,
    summary: post.summary ?? '',
    content_md: post.content_md,
    status: post.status,
    visibility: post.visibility,
    cover_file_id: post.cover_file_id,
    seo_title: post.seo_title ?? '',
    seo_description: post.seo_description ?? '',
  }
}

export function postToPreviewInput(post: AdminPostItem) {
  return {
    slug: post.slug,
    content_md: post.content_md,
  }
}

export function normalizePostForm(form: PostFormPayload): PostWritePayload {
  const { cover_file_id: coverFileId, ...formWithoutCover } = form
  const payload: PostWritePayload = {
    ...formWithoutCover,
    summary: nullableText(form.summary),
    seo_title: nullableText(form.seo_title),
    seo_description: nullableText(form.seo_description),
  }
  if (coverFileId !== null) {
    payload.cover_file_id = coverFileId
  }
  return payload
}

export function formatPostSaveError(error: unknown): string {
  if (!(error instanceof Error)) {
    return '保存失败'
  }
  if (error.message === 'file not found') {
    return '保存失败：封面 ID 或正文图片引用的文件不存在'
  }
  if (error.message === 'post slug already exists') {
    return '保存失败：Slug 已被其他文章使用'
  }
  if (error.message.startsWith('invalid encrypted request payload')) {
    return '保存失败：文章表单内容不完整'
  }
  return error.message || '保存失败'
}

function nullableText(value: string | null): string | null {
  const trimmed = value?.trim() ?? ''
  return trimmed === '' ? null : trimmed
}

function nextPostSlug(posts: AdminPostItem[]): string {
  const usedSlugs = new Set(posts.map((post) => post.slug))
  let index = posts.length + 1
  let slug = `post-${index}`
  while (usedSlugs.has(slug)) {
    index += 1
    slug = `post-${index}`
  }
  return slug
}
