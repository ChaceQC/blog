import { useState } from 'react'

import { Check, MessageSquare, ShieldAlert, Trash2, X } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { publicErrorMessage } from '../../api/client.ts'
import { ListPager } from '../../components/ListPager.tsx'
import {
  deleteAdminComment,
  listAdminComments,
  reviewAdminComment,
} from '../../features/comments/adminApi.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type {
  AdminCommentItem,
  AdminCommentReviewPayload,
  AdminCommentStatusFilter,
} from '../../features/comments/types.ts'

const STATUS_TABS: Array<{ label: string; value: AdminCommentStatusFilter }> = [
  { label: '待审核', value: 'pending' },
  { label: '已发布', value: 'published' },
  { label: '全部', value: 'all' },
]

const STATUS_LABELS = {
  pending: '待审核',
  published: '已发布',
  rejected: '已拒绝',
  deleted_by_author: '作者删除',
  deleted_by_admin: '管理员删除',
  spam: '垃圾',
} as const

const COMMENT_REVIEW_PAGE_SIZE = 10

function nextStatusForAction(payload: AdminCommentReviewPayload) {
  if (payload.action === 'approve') {
    return 'published'
  }
  if (payload.action === 'reject') {
    return 'rejected'
  }
  if (payload.action === 'spam') {
    return 'spam'
  }
  return 'deleted_by_admin'
}

function leavesStatusFilter(
  statusFilter: AdminCommentStatusFilter,
  comment: AdminCommentItem,
  payload: AdminCommentReviewPayload,
) {
  if (statusFilter === 'all' || comment.status !== statusFilter) {
    return false
  }
  return nextStatusForAction(payload) !== statusFilter
}

export function AdminCommentsPage() {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [statusFilter, setStatusFilter] =
    useState<AdminCommentStatusFilter>('pending')
  const [page, setPage] = useState(0)
  const commentsQuery = useQuery({
    queryKey: ['admin-comments', statusFilter, page],
    queryFn: ({ signal }) =>
      listAdminComments({
        status: statusFilter,
        limit: COMMENT_REVIEW_PAGE_SIZE,
        offset: page * COMMENT_REVIEW_PAGE_SIZE,
        signal,
      }),
  })
  const reviewMutation = useMutation({
    mutationFn: ({
      comment,
      payload,
    }: {
      comment: AdminCommentItem
      payload: AdminCommentReviewPayload
    }) => {
      const csrfToken = session?.csrfToken
      if (!csrfToken) {
        throw new Error('后台会话已失效')
      }
      if (payload.action === 'delete') {
        return deleteAdminComment(comment.id, csrfToken)
      }
      return reviewAdminComment(comment.id, payload, csrfToken)
    },
    onSuccess: (_, { comment, payload }) => {
      if (
        page > 0 &&
        commentsQuery.data?.items.length === 1 &&
        leavesStatusFilter(statusFilter, comment, payload)
      ) {
        setPage((current) => Math.max(0, current - 1))
      }
      queryClient.invalidateQueries({ queryKey: ['admin-comments'] })
      queryClient.invalidateQueries({ queryKey: ['public-comments'] })
      queryClient.invalidateQueries({ queryKey: ['public-post'] })
      queryClient.invalidateQueries({ queryKey: ['public-posts'] })
    },
  })
  const error = commentsQuery.error ?? reviewMutation.error
  const errorMessage = error
    ? publicErrorMessage(error, '评论审核暂时无法同步。')
    : null

  function runAction(
    comment: AdminCommentItem,
    payload: AdminCommentReviewPayload,
  ) {
    if (payload.action === 'delete' && !window.confirm('删除这条评论？')) {
      return
    }
    reviewMutation.mutate({ comment, payload })
  }

  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>评论</span>
        <h1>评论审核</h1>
      </section>

      <div className="admin-workspace admin-workspace--comments">
        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>
              <MessageSquare size={18} strokeWidth={1.8} aria-hidden="true" />
              评论队列
            </span>
            <small>{commentsQuery.data?.total ?? 0} 条</small>
          </div>
          <div className="admin-tabs">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                className={
                  statusFilter === tab.value ? 'admin-tab active' : 'admin-tab'
                }
                onClick={() => {
                  setStatusFilter(tab.value)
                  setPage(0)
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
          <div className="comment-review-list">
            {commentsQuery.data?.items.length === 0 ? (
              <p className="empty-state">没有需要处理的评论。</p>
            ) : null}
            {commentsQuery.data?.items.map((comment) => (
              <article className="comment-review-item" key={comment.id}>
                <header>
                  <strong>{comment.display_name}</strong>
                  <span>{STATUS_LABELS[comment.status]}</span>
                </header>
                <p>{comment.body_text}</p>
                <footer>
                  <small>
                    {comment.post_title} / #{comment.author_public_id} / 风险{' '}
                    {comment.risk_hash_prefix}
                  </small>
                  <div className="comment-review-actions">
                    {comment.status === 'pending' ? (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            runAction(comment, { action: 'approve' })
                          }
                        >
                          <Check size={15} strokeWidth={1.8} aria-hidden="true" />
                          通过
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            runAction(comment, {
                              action: 'reject',
                              reason_class: 'review_rejected',
                            })
                          }
                        >
                          <X size={15} strokeWidth={1.8} aria-hidden="true" />
                          拒绝
                        </button>
                      </>
                    ) : null}
                    <button
                      type="button"
                      onClick={() =>
                        runAction(comment, {
                          action: 'spam',
                          reason_class: 'spam',
                        })
                      }
                    >
                      <ShieldAlert
                        size={15}
                        strokeWidth={1.8}
                        aria-hidden="true"
                      />
                      垃圾
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        runAction(comment, {
                          action: 'delete',
                          reason_class: 'admin_deleted',
                        })
                      }
                    >
                      <Trash2 size={15} strokeWidth={1.8} aria-hidden="true" />
                      删除
                    </button>
                  </div>
                </footer>
              </article>
            ))}
          </div>
          <ListPager
            page={page}
            pageSize={COMMENT_REVIEW_PAGE_SIZE}
            totalItems={commentsQuery.data?.total ?? 0}
            isLoading={commentsQuery.isLoading || commentsQuery.isFetching}
            variant="admin"
            onPageChange={setPage}
          />
        </section>
      </div>
    </div>
  )
}
