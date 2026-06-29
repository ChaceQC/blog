import { Fragment, useMemo, useState } from 'react'

import { MessageCircle, Reply, Send, Trash2, X } from 'lucide-react'
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { publicErrorMessage } from '../../api/client.ts'
import {
  formatChinaShortDateTime,
  parseApiTime,
} from '../../utils/datetime.ts'
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

type CommentThread = {
  root: PublicCommentItem
  replies: PublicCommentItem[]
}

type CreateCommentVariables = {
  parentId: number | null
  bodyText: string
}

const ROOT_COMMENT_BATCH_SIZE = 5
const REPLY_BATCH_SIZE = 3
const COMMENT_PREVIEW_MAX_CHARS = 220
const COMMENT_PREVIEW_MAX_LINES = 6

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
  const [replyBodyText, setReplyBodyText] = useState('')
  const [replyTo, setReplyTo] = useState<PublicCommentItem | null>(null)
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const [visibleRootCount, setVisibleRootCount] = useState(
    ROOT_COMMENT_BATCH_SIZE,
  )
  const [visibleReplyCounts, setVisibleReplyCounts] = useState<
    Record<number, number>
  >({})
  const [expandedCommentIds, setExpandedCommentIds] = useState<Set<number>>(
    () => new Set(),
  )
  const commentsQuery = useInfiniteQuery({
    queryKey: ['public-comments', slug],
    queryFn: ({ pageParam, signal }) =>
      listPublicComments(slug, {
        limit: ROOT_COMMENT_BATCH_SIZE,
        offset: Number(pageParam),
        signal,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => {
      const loadedRootCount = pages.reduce(
        (count, page) => count + countRootComments(page.items),
        0,
      )
      return loadedRootCount < lastPage.thread_total ? loadedRootCount : undefined
    },
    enabled: slug.length > 0,
  })
  const ownedQuery = useQuery({
    queryKey: ['public-comments-owned', slug],
    queryFn: ({ signal }) =>
      listOwnedPublicComments(slug, { receipts: receiptPayload(slug) }, { signal }),
    enabled: slug.length > 0 && receiptPayload(slug).length > 0,
  })
  const createMutation = useMutation({
    mutationFn: async ({ parentId, bodyText: commentBody }: CreateCommentVariables) => {
      const [fingerprint, authorSecretProof] = await Promise.all([
        getVisitorFingerprint(),
        getCommentAuthorSecretProof(),
      ])
      return createPublicComment(slug, {
        parent_id: parentId,
        display_name: displayName.trim() || null,
        body_text: commentBody,
        author_secret_proof: authorSecretProof,
        fingerprint,
      })
    },
    onSuccess: (response, variables) => {
      saveDisplayNameDraft(displayName)
      const receiptSaved = saveCommentReceipt({
        comment_id: response.comment.id,
        post_slug: slug,
        delete_token: response.delete_token,
        created_at: new Date().toISOString(),
      })
      if (variables.parentId === null) {
        setBodyText('')
      } else {
        setReplyBodyText('')
        setReplyTo(null)
      }
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
      queryClient.invalidateQueries({ queryKey: ['public-comments', slug] })
      queryClient.invalidateQueries({ queryKey: ['public-post', slug] })
      queryClient.invalidateQueries({ queryKey: ['public-posts'] })
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
      queryClient.invalidateQueries({ queryKey: ['public-post', slug] })
      queryClient.invalidateQueries({ queryKey: ['public-posts'] })
    },
  })

  const publicComments = useMemo(
    () => commentsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [commentsQuery.data?.pages],
  )
  const publicThreadTotal =
    commentsQuery.data?.pages.at(-1)?.thread_total ?? publicComments.length
  const loadedPublicRootCount = useMemo(
    () => countRootComments(publicComments),
    [publicComments],
  )
  const comments = useMemo(
    () =>
      mergeComments(
        publicComments,
        ownedQuery.data?.items ?? [],
      ),
    [publicComments, ownedQuery.data?.items],
  )
  const threads = useMemo(() => buildCommentThreads(comments), [comments])
  const visibleThreads = visibleCommentThreads(threads, visibleRootCount, slug)
  const visibleThreadIds = new Set(visibleThreads.map((thread) => thread.root.id))
  const loadedHiddenRootCount = threads.filter(
    (thread) => !visibleThreadIds.has(thread.root.id),
  ).length
  const unloadedRootCount = Math.max(0, publicThreadTotal - loadedPublicRootCount)
  const hiddenRootCount = loadedHiddenRootCount + unloadedRootCount
  const visibleCount = commentsQuery.data?.pages.at(-1)?.total ?? initialCount
  const error = commentsQuery.error ?? ownedQuery.error ?? createMutation.error
  const errorMessage = error
    ? publicErrorMessage(error, '评论暂时无法同步。')
    : null
  const canSubmit = bodyText.trim().length > 0 && !createMutation.isPending
  const canSubmitReply =
    replyBodyText.trim().length > 0 && !createMutation.isPending

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
          createMutation.mutate({ parentId: null, bodyText })
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
        {visibleThreads.map((thread) => {
          const visibleReplies = visibleThreadReplies(
            thread.replies,
            visibleReplyCounts[thread.root.id] ?? REPLY_BATCH_SIZE,
            slug,
          )
          const visibleReplyIds = new Set(visibleReplies.map((reply) => reply.id))
          const hiddenReplyCount = thread.replies.filter(
            (reply) => !visibleReplyIds.has(reply.id),
          ).length

          return (
            <div className="comment-thread" key={thread.root.id}>
              <CommentRow
                comment={thread.root}
                deleteMutationPending={deleteMutation.isPending}
                expanded={expandedCommentIds.has(thread.root.id)}
                owned={hasCommentReceipt(thread.root.id, slug)}
                onDelete={(comment) => deleteMutation.mutate(comment)}
                onReply={startReply}
                onToggleExpanded={toggleExpandedComment}
              />
              {replyTo?.id === thread.root.id ? (
                <InlineReplyForm
                  canSubmit={canSubmitReply}
                  displayName={displayName}
                  isPending={createMutation.isPending}
                  target={thread.root}
                  value={replyBodyText}
                  onCancel={cancelReply}
                  onDisplayNameChange={setDisplayName}
                  onSubmit={() =>
                    createMutation.mutate({
                      parentId: thread.root.id,
                      bodyText: replyBodyText,
                    })
                  }
                  onValueChange={setReplyBodyText}
                />
              ) : null}
              {visibleReplies.length > 0 ? (
                <div className="comment-thread__replies">
                  {visibleReplies.map((reply) => (
                    <Fragment key={reply.id}>
                      <CommentRow
                        comment={reply}
                        deleteMutationPending={deleteMutation.isPending}
                        expanded={expandedCommentIds.has(reply.id)}
                        owned={hasCommentReceipt(reply.id, slug)}
                        onDelete={(comment) => deleteMutation.mutate(comment)}
                        onReply={startReply}
                        onToggleExpanded={toggleExpandedComment}
                      />
                      {replyTo?.id === reply.id ? (
                        <InlineReplyForm
                          canSubmit={canSubmitReply}
                          displayName={displayName}
                          isPending={createMutation.isPending}
                          target={reply}
                          value={replyBodyText}
                          onCancel={cancelReply}
                          onDisplayNameChange={setDisplayName}
                          onSubmit={() =>
                            createMutation.mutate({
                              parentId: reply.id,
                              bodyText: replyBodyText,
                            })
                          }
                          onValueChange={setReplyBodyText}
                        />
                      ) : null}
                    </Fragment>
                  ))}
                </div>
              ) : null}
              {hiddenReplyCount > 0 ? (
                <button
                  className="comment-more-button comment-more-button--small"
                  type="button"
                  onClick={() =>
                    setVisibleReplyCounts((current) => ({
                      ...current,
                      [thread.root.id]:
                        (current[thread.root.id] ?? REPLY_BATCH_SIZE) +
                        REPLY_BATCH_SIZE,
                    }))
                  }
                >
                  显示更多回复（剩余 {hiddenReplyCount} 条）
                </button>
              ) : null}
            </div>
          )
        })}
        {hiddenRootCount > 0 ? (
          <button
            className="comment-more-button"
            disabled={commentsQuery.isFetchingNextPage}
            type="button"
            onClick={showMoreRootComments}
          >
            {commentsQuery.isFetchingNextPage
              ? '正在加载更多评论'
              : `显示更多评论（剩余 ${hiddenRootCount} 条）`}
          </button>
        ) : null}
      </div>
    </section>
  )

  function cancelReply() {
    setReplyTo(null)
    setReplyBodyText('')
  }

  function startReply(comment: PublicCommentItem) {
    setReplyTo(comment)
    setReplyBodyText('')
  }

  function toggleExpandedComment(commentId: number) {
    setExpandedCommentIds((current) => {
      const next = new Set(current)
      if (next.has(commentId)) {
        next.delete(commentId)
      } else {
        next.add(commentId)
      }
      return next
    })
  }

  function showMoreRootComments() {
    const nextVisibleRootCount = visibleRootCount + ROOT_COMMENT_BATCH_SIZE
    setVisibleRootCount(nextVisibleRootCount)
    if (
      nextVisibleRootCount > loadedPublicRootCount &&
      commentsQuery.hasNextPage &&
      !commentsQuery.isFetchingNextPage
    ) {
      void commentsQuery.fetchNextPage()
    }
  }
}

function InlineReplyForm({
  canSubmit,
  displayName,
  isPending,
  target,
  value,
  onCancel,
  onDisplayNameChange,
  onSubmit,
  onValueChange,
}: {
  canSubmit: boolean
  displayName: string
  isPending: boolean
  target: PublicCommentItem
  value: string
  onCancel: () => void
  onDisplayNameChange: (value: string) => void
  onSubmit: () => void
  onValueChange: (value: string) => void
}) {
  return (
    <form
      className="comment-form comment-form--inline"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="comment-form__replying">
        <span>回复 @{target.display_name}</span>
        <button type="button" onClick={onCancel}>
          <X size={15} strokeWidth={1.8} aria-hidden="true" />
          取消
        </button>
      </div>
      <label>
        昵称
        <input
          value={displayName}
          maxLength={32}
          onChange={(event) => onDisplayNameChange(event.target.value)}
          placeholder="匿名读者"
        />
      </label>
      <label>
        回复
        <textarea
          value={value}
          maxLength={2000}
          rows={3}
          onChange={(event) => onValueChange(event.target.value)}
          placeholder="写下回复"
        />
      </label>
      <div className="comment-form__footer">
        <span>回复提交后也会先进入审核。</span>
        <button type="submit" disabled={!canSubmit || isPending}>
          <Send size={16} strokeWidth={1.8} aria-hidden="true" />
          发送
        </button>
      </div>
    </form>
  )
}

function CommentRow({
  comment,
  deleteMutationPending,
  expanded,
  owned,
  onDelete,
  onReply,
  onToggleExpanded,
}: {
  comment: PublicCommentItem
  deleteMutationPending: boolean
  expanded: boolean
  owned: boolean
  onDelete: (comment: PublicCommentItem) => void
  onReply: (comment: PublicCommentItem) => void
  onToggleExpanded: (commentId: number) => void
}) {
  const bodyLong = isLongComment(comment.body_text)
  const bodyText =
    bodyLong && !expanded ? collapsedCommentText(comment.body_text) : comment.body_text

  return (
    <article
      className={
        comment.parent_id === null
          ? 'comment-item'
          : 'comment-item comment-item--reply'
      }
    >
      <div className="comment-item__avatar" aria-hidden="true">
        {comment.author_public_id.slice(0, 2)}
      </div>
      <div className="comment-item__body">
        <header>
          <strong>{comment.display_name}</strong>
          {comment.reply_to_id &&
          comment.reply_to_display_name &&
          comment.parent_id !== null ? (
            <span className="comment-item__reply-target">
              回复 @{comment.reply_to_display_name}
            </span>
          ) : null}
          <StatusBadge status={comment.status} owned={owned} />
        </header>
        <p>{bodyText}</p>
        {bodyLong ? (
          <button
            aria-expanded={expanded}
            className="comment-expand-button"
            type="button"
            onClick={() => onToggleExpanded(comment.id)}
          >
            {expanded ? '收起' : '展开'}
          </button>
        ) : null}
        <footer>
          <time dateTime={comment.created_at}>
            {formatCommentTime(comment.created_at)}
          </time>
          {comment.status === 'published' ? (
            <button
              type="button"
              className="comment-delete-button"
              onClick={() => onReply(comment)}
            >
              <Reply size={15} strokeWidth={1.8} aria-hidden="true" />
              回复
            </button>
          ) : null}
          {owned &&
          (comment.status === 'pending' || comment.status === 'published') ? (
            <button
              type="button"
              className="comment-delete-button"
              disabled={deleteMutationPending}
              onClick={() => {
                if (window.confirm('删除这条评论？')) {
                  onDelete(comment)
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

function buildCommentThreads(comments: PublicCommentItem[]): CommentThread[] {
  const rootIds = new Set(
    comments
      .filter((comment) => comment.parent_id === null)
      .map((comment) => comment.id),
  )
  const repliesByRoot = new Map<number, PublicCommentItem[]>()
  for (const comment of comments) {
    if (comment.parent_id === null) {
      continue
    }
    const replies = repliesByRoot.get(comment.parent_id) ?? []
    replies.push(comment)
    repliesByRoot.set(comment.parent_id, replies)
  }

  const threads = comments
    .filter((comment) => comment.parent_id === null)
    .map((root) => ({
      root,
      replies: repliesByRoot.get(root.id) ?? [],
    }))
  for (const comment of comments) {
    if (comment.parent_id !== null && !rootIds.has(comment.parent_id)) {
      threads.push({ root: comment, replies: [] })
    }
  }
  return threads
}

function visibleCommentThreads(
  threads: CommentThread[],
  visibleCount: number,
  slug: string,
): CommentThread[] {
  const visible = threads.slice(0, visibleCount)
  const visibleIds = new Set(visible.map((thread) => thread.root.id))
  for (const thread of threads.slice(visibleCount)) {
    if (threadHasOwnedComment(thread, slug) && !visibleIds.has(thread.root.id)) {
      visible.push(thread)
      visibleIds.add(thread.root.id)
    }
  }
  return visible
}

function visibleThreadReplies(
  replies: PublicCommentItem[],
  visibleCount: number,
  slug: string,
): PublicCommentItem[] {
  const visible = replies.slice(0, visibleCount)
  const visibleIds = new Set(visible.map((reply) => reply.id))
  for (const reply of replies.slice(visibleCount)) {
    if (hasCommentReceipt(reply.id, slug) && !visibleIds.has(reply.id)) {
      visible.push(reply)
      visibleIds.add(reply.id)
    }
  }
  return visible
}

function threadHasOwnedComment(thread: CommentThread, slug: string): boolean {
  return (
    hasCommentReceipt(thread.root.id, slug) ||
    thread.replies.some((reply) => hasCommentReceipt(reply.id, slug))
  )
}

function countRootComments(comments: PublicCommentItem[]): number {
  return comments.filter((comment) => comment.parent_id === null).length
}

function isLongComment(value: string): boolean {
  return (
    Array.from(value).length > COMMENT_PREVIEW_MAX_CHARS ||
    value.split('\n').length > COMMENT_PREVIEW_MAX_LINES
  )
}

function collapsedCommentText(value: string): string {
  const linePreview = value
    .split('\n')
    .slice(0, COMMENT_PREVIEW_MAX_LINES)
    .join('\n')
  const characters = Array.from(linePreview)
  const preview =
    characters.length > COMMENT_PREVIEW_MAX_CHARS
      ? characters.slice(0, COMMENT_PREVIEW_MAX_CHARS).join('')
      : linePreview
  return `${preview.trimEnd()}...`
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
  return formatChinaShortDateTime(value, value)
}

function dateTime(value: string): number {
  const time = parseApiTime(value)
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
