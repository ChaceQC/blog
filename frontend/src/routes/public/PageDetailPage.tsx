import { ArrowLeft } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import {
  ApiError,
  publicErrorMessage,
} from '../../api/client.ts'
import { MathHtml } from '../../components/MathHtml.tsx'
import { getPublicPage } from '../../features/posts/api.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { siteSettings } from '../../features/settings/siteSettings.ts'

export function PageDetailPage() {
  const { slug = '' } = useParams()
  const { data: page, error: pageError, isError, isLoading } = useQuery({
    queryKey: ['public-page', slug],
    queryFn: ({ signal }) => getPublicPage(slug, { signal }),
    enabled: slug.length > 0,
  })
  usePageSeo({
    title: page?.seo_title ?? page?.title ?? '页面',
    description:
      page?.seo_description ?? `${siteSettings.title}的独立页面`,
    path: slug ? `/${slug}` : '/',
    type: 'article',
  })
  const isPageNotFound = pageError instanceof ApiError && pageError.status === 404
  const pageErrorTitle = isPageNotFound ? '没有找到这个页面' : '页面暂时无法打开'
  const pageErrorDescription = isPageNotFound
    ? '它可能还未发布，或者地址已经变更。'
    : publicErrorMessage(
        pageError,
        '网络或加密会话暂时不可用，请返回首页稍后再试。',
      )

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
          <h1>{pageErrorTitle}</h1>
          <p>{pageErrorDescription}</p>
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
