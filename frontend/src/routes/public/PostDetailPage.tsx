import { ArrowLeft, Clock3 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { MathHtml } from '../../components/MathHtml.tsx'
import { getPublicPost } from '../../features/posts/api.ts'
import {
  formatPostDate,
  getReadingMinutes,
  postCoverUrl,
} from '../../features/posts/postMeta.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'

export function PostDetailPage() {
  const { slug = '' } = useParams()
  const { data: post, isError, isLoading } = useQuery({
    queryKey: ['public-post', slug],
    queryFn: ({ signal }) => getPublicPost(slug, { signal }),
    enabled: slug.length > 0,
  })
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
          {post.category_names.map((category) => (
            <span key={category}>{category}</span>
          ))}
          <span>
            <Clock3 size={16} strokeWidth={1.8} aria-hidden="true" />
            {getReadingMinutes(post.word_count)} 分钟
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
    </article>
  )
}
