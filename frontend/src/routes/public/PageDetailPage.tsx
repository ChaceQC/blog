import { ArrowLeft } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { MathHtml } from '../../components/MathHtml.tsx'
import { getPublicPage } from '../../features/posts/api.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'

export function PageDetailPage() {
  const { slug = '' } = useParams()
  const { data: page, isError, isLoading } = useQuery({
    queryKey: ['public-page', slug],
    queryFn: () => getPublicPage(slug),
    enabled: slug.length > 0,
  })
  usePageSeo({
    title: page?.seo_title ?? page?.title ?? '页面',
    description:
      page?.seo_description ?? `${siteSettings.title}的独立页面`,
    path: slug ? `/${slug}` : '/',
    type: 'article',
  })

  if (isLoading) {
    return (
      <div className="page-flow page-flow--narrow">
        <p className="empty-state">正在打开页面。</p>
      </div>
    )
  }

  if (isError || !page) {
    return (
      <div className="page-flow page-flow--narrow">
        <section className="page-heading">
          <small>PAGE</small>
          <h1>没有找到这个页面</h1>
          <p>它可能还未发布，或者地址已经变更。</p>
        </section>
        <Link className="timeline-link" to="/">
          <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
          返回首页
        </Link>
      </div>
    )
  }

  return (
    <article className="page-flow page-flow--narrow post-detail">
      <Link className="timeline-link" to="/">
        <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
        返回首页
      </Link>
      <header className="page-heading post-detail__header">
        <small>PAGE</small>
        <h1>{page.seo_title ?? page.title}</h1>
        {page.seo_description ? <p>{page.seo_description}</p> : null}
      </header>
      <MathHtml className="post-prose" html={page.content_html} />
    </article>
  )
}
