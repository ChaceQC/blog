import { useEffect, useMemo, useRef, useState } from 'react'

import { ArrowLeft, Clock3, Eye, Heart, MessageCircle } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import {
  ApiError,
  isRateLimitError,
  publicErrorMessage,
} from '../../api/client.ts'
import { MathHtml } from '../../components/MathHtml.tsx'
import {
  getPublicPost,
  recordPublicPostView,
  setPublicPostLike,
} from '../../features/posts/api.ts'
import {
  formatPostDate,
  formatPostWordCount,
  getReadingMinutes,
  postCoverUrl,
} from '../../features/posts/postMeta.ts'
import { PostComments } from '../../features/posts/PostComments.tsx'
import {
  getStableVisitorFingerprintFallback,
  getVisitorFingerprint,
} from '../../features/posts/visitorFingerprint.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'
import type {
  PublicPostInteractionState,
  PublicPostListResponse,
} from '../../features/posts/types.ts'

type SlugInteractionState = {
  slug: string
  state: PublicPostInteractionState
}

export function PostDetailPage() {
  const { slug = '' } = useParams()
  const queryClient = useQueryClient()
  const [interactionState, setInteractionState] =
    useState<SlugInteractionState | null>(null)
  const recordedViewSlugRef = useRef<string | null>(null)
  const { data: post, error: postError, isError, isLoading } = useQuery({
    queryKey: ['public-post', slug],
    queryFn: ({ signal }) => getPublicPost(slug, { signal }),
    enabled: slug.length > 0,
  })
  const viewMutation = useMutation({
    mutationFn: async () => {
      const fingerprint = await getVisitorFingerprint()
      return recordPublicPostView(slug, { fingerprint })
    },
    onSuccess: (state) => {
      setInteractionState({ slug, state })
      updatePostInteractionCaches(queryClient, slug, state)
    },
  })
  const likeMutation = useMutation({
    mutationFn: async (liked: boolean) => {
      const fingerprint = await getVisitorFingerprint()
      try {
        return await setPublicPostLike(slug, { fingerprint, liked })
      } catch (error) {
        if (!liked || !isPostInteractionRiskLimit(error)) {
          throw error
        }
        const fallbackFingerprint = await getStableVisitorFingerprintFallback()
        return setPublicPostLike(slug, {
          fingerprint: fallbackFingerprint,
          liked,
        })
      }
    },
    onSuccess: (state) => {
      setInteractionState({ slug, state })
      updatePostInteractionCaches(queryClient, slug, state)
    },
  })
  const currentInteractionState = useMemo(
    () => interactionState?.slug === slug ? interactionState.state : null,
    [interactionState, slug],
  )
  const isPostNotFound = postError instanceof ApiError && postError.status === 404
  const postErrorTitle = isPostNotFound ? '没有找到这篇文章' : '文章暂时无法打开'
  const postErrorDescription = isPostNotFound
    ? '它可能还未发布，或者已经被设为隐藏。'
    : publicErrorMessage(
        postError,
        '网络或加密会话暂时不可用，请返回列表稍后再试。',
      )
  const interactionError =
    viewMutation.error ?? likeMutation.error
  const interactionErrorMessage = interactionError
    ? publicErrorMessage(interactionError, '互动状态暂时无法同步。')
    : null

  useEffect(() => {
    if (
      !post ||
      !slug ||
      viewMutation.isPending ||
      currentInteractionState ||
      recordedViewSlugRef.current === slug
    ) {
      return
    }
    recordedViewSlugRef.current = slug
    viewMutation.mutate()
  }, [currentInteractionState, post, slug, viewMutation])

  usePageSeo({
    title: post?.seo_title ?? post?.title ?? '文章',
    description:
      post?.seo_description ?? post?.summary ?? `${siteSettings.title}文章`,
    path: slug ? `/posts/${slug}` : '/posts',
    keywords: post?.seo_keywords ?? post?.tag_names.join(',') ?? null,
    imageUrl: post ? postCoverUrl(post) : null,
    type: 'article',
  })

  if (isLoading) {
    return (
      <div className="page-flow page-flow--narrow">
        <p className="empty-state">正在打开文章。</p>
      </div>
    )
  }

  if (isError || !post) {
    return (
      <div className="page-flow page-flow--narrow">
        <section className="page-heading">
          <small>POST</small>
          <h1>{postErrorTitle}</h1>
          <p>{postErrorDescription}</p>
        </section>
        <Link className="timeline-link" to="/posts">
          <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
          返回文章列表
        </Link>
      </div>
    )
  }

  const viewCount = currentInteractionState?.view_count ?? post.view_count
  const likeCount = currentInteractionState?.like_count ?? post.like_count
  const liked = currentInteractionState?.liked ?? false

  return (
    <>
      <article className="page-flow page-flow--narrow post-detail">
        <Link className="timeline-link" to="/posts">
          <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
          返回文章列表
        </Link>
        <header className="page-heading post-detail__header">
          <small>POST</small>
          <h1>{post.seo_title ?? post.title}</h1>
          <p>{post.summary ?? post.seo_description ?? '这篇文章暂时没有摘要。'}</p>
          <div className="post-detail__meta">
            <span>{formatPostDate(post.published_at)}</span>
            {post.category_names.map((category) => (
              <span key={category}>{category}</span>
            ))}
            <span>
              <Clock3 size={16} strokeWidth={1.8} aria-hidden="true" />
              {getReadingMinutes(post.word_count)} 分钟
            </span>
            <span>{formatPostWordCount(post.word_count)}</span>
            <span>
              <Eye size={16} strokeWidth={1.8} aria-hidden="true" />
              {viewCount}
            </span>
            <span>
              <MessageCircle size={16} strokeWidth={1.8} aria-hidden="true" />
              {post.comment_count}
            </span>
          </div>
          {post.tag_names.length > 0 ? (
            <div className="post-taxonomy">
              {post.tag_names.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
          ) : null}
        </header>
        <MathHtml
          className="post-prose"
          html={post.content_html}
        />
        <PostComments
          key={slug}
          slug={slug}
          initialCount={post.comment_count}
        />
      </article>
      <div className="post-detail-actions" aria-label="文章互动">
        {interactionErrorMessage ? (
          <span className="post-detail-actions__notice">
            {interactionErrorMessage}
          </span>
        ) : null}
        <span className="post-detail-actions__views" aria-label={`浏览 ${viewCount}`}>
          <Eye size={16} strokeWidth={1.8} aria-hidden="true" />
          {viewCount}
        </span>
        <button
          type="button"
          className={liked ? 'post-like-button is-liked' : 'post-like-button'}
          aria-pressed={liked}
          aria-label={liked ? '取消点赞' : '点赞'}
          disabled={likeMutation.isPending}
          onClick={() => likeMutation.mutate(!liked)}
        >
          <Heart size={19} strokeWidth={liked ? 2.4 : 1.9} aria-hidden="true" />
          <span>{likeCount}</span>
        </button>
      </div>
    </>
  )
}

function isPostInteractionRiskLimit(error: unknown): boolean {
  return (
    isRateLimitError(error) &&
    error instanceof Error &&
    error.message === 'post interaction risk limited'
  )
}

function updatePostInteractionCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  slug: string,
  state: PublicPostInteractionState,
) {
  queryClient.setQueryData(['public-post', slug], (current: unknown) =>
    updatePostLikeFields(current, state),
  )
  queryClient.setQueriesData(
    { queryKey: ['public-posts'] },
    (current: unknown) => {
      if (!isPublicPostListResponse(current)) {
        return current
      }
      return {
        ...current,
        items: current.items.map((item) =>
          item.slug === slug ? updatePostLikeFields(item, state) : item,
        ),
      }
    },
  )
}

function updatePostLikeFields<T>(value: T, state: PublicPostInteractionState): T {
  if (!value || typeof value !== 'object') {
    return value
  }
  return {
    ...value,
    view_count: state.view_count,
    like_count: state.like_count,
  }
}

function isPublicPostListResponse(
  value: unknown,
): value is PublicPostListResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'items' in value &&
    Array.isArray((value as { items?: unknown }).items)
  )
}
