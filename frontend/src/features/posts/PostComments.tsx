import { useMemo, useState } from 'react'

import { MessageCircle, Reply, Send, Trash2, X } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { publicErrorMessage } from '../../api/client.ts'
import {
  createPublicComment,
  deletePublicComment,
  listOwnedPublicComments,
  listPublicComments,
} from './api.ts'
import {
  getCommentAuthorSecretProof,
  hasCommentReceipt,
  receiptPayload,
  receiptToken,
  removeCommentReceipt,
  saveCommentReceipt,
} from './commentReceipts.ts'
import { getVisitorFingerprint } from './visitorFingerprint.ts'

import type { PublicCommentItem } from './types.ts'

type PostCommentsProps = {
  slug: string
  initialCount: number
}

const STATUS_LABELS = {
  pending: '审核中',
  published: '已发布',
  rejected: '未通过',
  deleted_by_author: '已删除',
  deleted_by_admin: '已删除',
  spam: '未通过',
} as const

export function PostComments({ slug, initialCount }: PostCommentsProps) {
  const queryClient = useQueryClient()
  const [displayName, setDisplayName] = useState(() => readDisplayNameDraft())
  const [bodyText, setBodyText] = useState('')
  const [replyTo, setReplyTo] = useState<PublicCommentItem | null>(null)
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const commentsQuery = useQuery({
    queryKey: ['public-comments', slug],
    queryFn: ({ signal }) => listPublicComments(slug, { signal }),
    enabled: slug.length > 0,
  })
  const ownedQuery = useQuery({
    queryKey: ['public-comments-owned', slug],
    queryFn: ({ signal }) =>
      listOwnedPublicComments(slug, { receipts: receiptPayload(slug) }, { signal }),
    enabled: slug.length > 0 && receiptPayload(slug).length > 0,
  })
  const createMutation = useMutation({
    mutationFn: async () => {
      const [fingerprint, authorSecretProof] = await Promise.all([
        getVisitorFingerprint(),
        getCommentAuthorSecretProof(),
      ])
      return createPublicComment(slug, {
        parent_id: replyTo?.id ?? null,
        display_name: displayName.trim() || null,
        body_text: bodyText,
        author_secret_proof: authorSecretProof,
        fingerprint,
      })
    },
    onSuccess: (response) => {
      saveDisplayNameDraft(displayName)
      const receiptSaved = saveCommentReceipt({
        comment_id: response.comment.id,
        post_slug: slug,
        delete_token: response.delete_token,
        created_at: new Date().toISOString(),
      })
      setBodyText('')
      setReplyTo(null)
      setFormMessage(
        receiptSaved
          ? response.message
          : `评论已提交，等待审核。请临时保存删除凭证：${response.delete_token}`,
      )
      queryClient.setQueryData(['public-comments-owned', slug], (current) => {
        if (!isOwnedCommentResponse(current)) {
          return { items: [response.comment] }
        }
        return { items: mergeComments(current.items, [response.comment]) }
      })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: async (comment: PublicCommentItem) => {
      const token = receiptToken(comment.id, slug)
      if (!token) {
        throw new Error('缺少删除凭证')
      }
      return deletePublicComment(slug, comment.id, { delete_token: token })
    },
    onSuccess: (response) => {
      removeCommentReceipt(response.id)
      queryClient.invalidateQueries({ queryKey: ['public-comments', slug] })
      queryClient.invalidateQueries({ queryKey: ['public-comments-owned', slug] })
    },
  })
  const comments = useMemo(
    () =>
      mergeComments(
        commentsQuery.data?.items ?? [],
        ownedQuery.data?.items ?? [],
      ),
    [commentsQuery.data?.items, ownedQuery.data?.items],
  )
  const visibleCount = commentsQuery.data?.total ?? initialCount
  const error = commentsQuery.error ?? ownedQuery.error ?? createMutation.error
  const errorMessage = error
    ? publicErrorMessage(error, '评论暂时无法同步。')
    : null
  const canSubmit = bodyText.trim().length > 0 && !createMutation.isPending

  return (
    <section className="post-comments" aria-labelledby="post-comments-title">
      <div className="section-heading">
        <span id="post-comments-title">
          <MessageCircle size={18} strokeWidth={1.8} aria-hidden="true" />
          评论
        </span>
        <small>{visibleCount} 条已发布</small>
      </div>

      <form
        className="comment-form"
        onSubmit={(event) => {
          event.preventDefault()
          setFormMessage(null)
          createMutation.mutate()
        }}
      >
        <label>
          昵称
          <input
            value={displayName}
            maxLength={32}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="匿名读者"
          />
        </label>
        <label>
          评论
          <textarea
            value={bodyText}
            maxLength={2000}
            rows={5}
            onChange={(event) => setBodyText(event.target.value)}
            placeholder="写下想说的话"
          />
        </label>
        {replyTo ? (
          <div className="comment-form__replying">
            <span>回复 {replyTo.display_name}</span>
            <button type="button" onClick={() => setReplyTo(null)}>
              <X size={15} strokeWidth={1.8} aria-hidden="true" />
              取消
            </button>
          </div>
        ) : null}
        <div className="comment-form__footer">
          <span>
            {formMessage ?? '提交后会先进入审核，当前浏览器可看到审核状态。'}
          </span>
          <button type="submit" disabled={!canSubmit}>
            <Send size={16} strokeWidth={1.8} aria-hidden="true" />
            发送
          </button>
        </div>
        {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      </form>

      <div className="comment-list">
        {comments.length === 0 && !commentsQuery.isLoading ? (
          <p className="empty-state">还没有评论。</p>
        ) : null}
        {comments.map((comment) => {
          const owned = hasCommentReceipt(comment.id, slug)
          return (
            <article
              className={
                comment.parent_id === null
                  ? 'comment-item'
                  : 'comment-item comment-item--reply'
              }
              key={comment.id}
            >
              <div className="comment-item__avatar" aria-hidden="true">
                {comment.author_public_id.slice(0, 2)}
              </div>
              <div className="comment-item__body">
                <header>
                  <strong>{comment.display_name}</strong>
                  <StatusBadge status={comment.status} owned={owned} />
                </header>
                <p>{comment.body_text}</p>
                <footer>
                  <time dateTime={comment.created_at}>
                    {formatCommentTime(comment.created_at)}
                  </time>
                  {comment.parent_id === null &&
                  comment.status === 'published' ? (
                    <button
                      type="button"
                      className="comment-delete-button"
                      onClick={() => setReplyTo(comment)}
                    >
                      <Reply size={15} strokeWidth={1.8} aria-hidden="true" />
                      回复
                    </button>
                  ) : null}
                  {owned &&
                  (comment.status === 'pending' ||
                    comment.status === 'published') ? (
                    <button
                      type="button"
                      className="comment-delete-button"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (window.confirm('删除这条评论？')) {
                          deleteMutation.mutate(comment)
                        }
                      }}
                    >
                      <Trash2 size={15} strokeWidth={1.8} aria-hidden="true" />
                      删除
                    </button>
                  ) : null}
                </footer>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function StatusBadge({
  status,
  owned,
}: {
  status: PublicCommentItem['status']
  owned: boolean
}) {
  if (status === 'published' && !owned) {
    return null
  }
  const variant =
    status === 'pending'
      ? 'pending'
      : status === 'published'
        ? 'published'
        : 'muted'
  return (
    <small className={`comment-status comment-status--${variant}`}>
      {STATUS_LABELS[status]}
    </small>
  )
}

function mergeComments(
  publicComments: PublicCommentItem[],
  ownedComments: PublicCommentItem[],
): PublicCommentItem[] {
  const items = new Map<number, PublicCommentItem>()
  for (const comment of publicComments) {
    items.set(comment.id, comment)
  }
  for (const comment of ownedComments) {
    items.set(comment.id, comment)
  }
  return Array.from(items.values()).sort((left, right) => {
    const leftParent = left.parent_id ?? left.id
    const rightParent = right.parent_id ?? right.id
    if (leftParent !== rightParent) {
      return leftParent - rightParent
    }
    if (left.parent_id === null && right.parent_id !== null) {
      return -1
    }
    if (left.parent_id !== null && right.parent_id === null) {
      return 1
    }
    const timeDelta = dateTime(left.created_at) - dateTime(right.created_at)
    return timeDelta === 0 ? left.id - right.id : timeDelta
  })
}

function isOwnedCommentResponse(
  value: unknown,
): value is { items: PublicCommentItem[] } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'items' in value &&
    Array.isArray((value as { items?: unknown }).items)
  )
}

function formatCommentTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function dateTime(value: string): number {
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

function readDisplayNameDraft(): string {
  try {
    return window.localStorage.getItem('blog.public.comment.display_name.v1') ?? ''
  } catch {
    return ''
  }
}

function saveDisplayNameDraft(value: string): void {
  try {
    window.localStorage.setItem(
      'blog.public.comment.display_name.v1',
      value.trim().slice(0, 32),
    )
  } catch {
    // 昵称只是便利项，保存失败不影响提交。
  }
}
