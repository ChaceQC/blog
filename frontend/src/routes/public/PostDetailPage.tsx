import { ArrowLeft, Clock3 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { MathHtml } from '../../components/MathHtml.tsx'
import { getPublicPost } from '../../features/posts/api.ts'
import {
  formatPostDate,
  getReadingMinutes,
  publicApiAssetUrl,
} from '../../features/posts/postMeta.ts'

export function PostDetailPage() {
  const { slug = '' } = useParams()
  const { data: post, isError, isLoading } = useQuery({
    queryKey: ['public-post', slug],
    queryFn: () => getPublicPost(slug),
    enabled: slug.length > 0,
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
          <h1>没有找到这篇文章</h1>
          <p>它可能还未发布，或者已经被设为隐藏。</p>
        </section>
        <Link className="timeline-link" to="/posts">
          <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
          返回文章列表
        </Link>
      </div>
    )
  }

  return (
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
          <span>
            <Clock3 size={16} strokeWidth={1.8} aria-hidden="true" />
            {getReadingMinutes(post.word_count)} 分钟
          </span>
        </div>
      </header>
      {post.cover_image_url ? (
        <figure className="post-detail__cover">
          <img
            alt={post.title}
            src={publicApiAssetUrl(post.cover_image_url)}
          />
        </figure>
      ) : null}
      <MathHtml
        className="post-prose"
        html={post.content_html}
      />
    </article>
  )
}
