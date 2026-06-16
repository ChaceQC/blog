import { ArrowLeft, Clock3 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'

import { MathHtml } from '../../components/MathHtml.tsx'
import { getPublicPost } from '../../features/posts/api.ts'
import {
  formatPostDate,
  getReadingMinutes,
  postCoverUrl,
} from '../../features/posts/postMeta.ts'

export function PostDetailPage() {
  const { slug = '' } = useParams()
  const { data: post, isError, isLoading } = useQuery({
    queryKey: ['public-post', slug],
    queryFn: () => getPublicPost(slug),
    enabled: slug.length > 0,
  })

  useEffect(() => {
    if (!post) {
      return
    }
    const previousTitle = document.title
    const nextTitle = post.seo_title ?? post.title
    document.title = `${nextTitle} | 静默书房`
    setMetaContent(
      'description',
      post.seo_description ?? post.summary ?? '静默书房文章',
    )
    setMetaContent('keywords', post.seo_keywords ?? post.tag_names.join(','))
    return () => {
      document.title = previousTitle
    }
  }, [post])

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
      <figure className="post-detail__cover">
        <img
          alt={post.title}
          src={postCoverUrl(post)}
        />
      </figure>
      <MathHtml
        className="post-prose"
        html={post.content_html}
      />
    </article>
  )
}

function setMetaContent(name: string, content: string) {
  let meta = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)
  if (!meta) {
    meta = document.createElement('meta')
    meta.name = name
    document.head.append(meta)
  }
  meta.content = content
}
