import type { PublicCommentStatus } from '../posts/types.ts'

export type AdminCommentItem = {
  id: number
  post_id: number
  post_title: string
  post_slug: string
  parent_id: number | null
  reply_to_id: number | null
  reply_to_display_name: string | null
  status: PublicCommentStatus
  display_name: string
  author_public_id: string
  body_text: string
  reply_count: number
  risk_hash_prefix: string
  created_at: string
  reviewed_at: string | null
  reviewed_by: number | null
  deleted_at: string | null
  deleted_reason: string | null
}

export type AdminCommentListResponse = {
  items: AdminCommentItem[]
  total: number
}

export type AdminCommentStatusFilter =
  | 'all'
  | 'pending'
  | 'published'
  | 'rejected'
  | 'deleted_by_author'
  | 'deleted_by_admin'
  | 'spam'

export type AdminCommentReviewPayload = {
  action: 'approve' | 'reject' | 'spam' | 'delete'
  reason_class?: string | null
}
