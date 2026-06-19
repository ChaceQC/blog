import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { getPublicSiteProfile } from '../settings/api.ts'
import { siteSettings } from '../settings/siteSettings.ts'

type PageSeoOptions = {
  title: string
  description: string
  path: string
  keywords?: string | null
  imageUrl?: string | null
  siteName?: string
  type?: 'website' | 'article'
}

export function usePageSeo({
  title,
  description,
  path,
  keywords,
  imageUrl,
  siteName,
  type = 'website',
}: PageSeoOptions) {
  const { data: siteProfile } = useQuery({
    queryKey: ['public-site-profile'],
    queryFn: ({ signal }) => getPublicSiteProfile({ signal }),
  })
  const effectiveSiteName = siteName ?? siteProfile?.title ?? siteSettings.title

  useEffect(() => {
    const fullTitle =
      title === effectiveSiteName ? title : `${title} | ${effectiveSiteName}`
    const canonicalUrl = absoluteUrl(path)
    const absoluteImageUrl = imageUrl ? absoluteUrl(imageUrl) : null

    document.documentElement.dataset.pageSeo = 'active'
    document.title = fullTitle
    setMeta('name', 'description', description)
    setMeta('name', 'keywords', keywords ?? null)
    setCanonical(canonicalUrl)
    setMeta('property', 'og:site_name', effectiveSiteName)
    setMeta('property', 'og:type', type)
    setMeta('property', 'og:title', title)
    setMeta('property', 'og:description', description)
    setMeta('property', 'og:url', canonicalUrl)
    setMeta('property', 'og:image', absoluteImageUrl)

    return () => {
      delete document.documentElement.dataset.pageSeo
    }
  }, [description, effectiveSiteName, imageUrl, keywords, path, title, type])
}

function absoluteUrl(value: string): string {
  return new URL(value, window.location.origin).toString()
}

function setCanonical(href: string) {
  let link = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'canonical'
    document.head.append(link)
  }
  link.href = href
}

function setMeta(
  attribute: 'name' | 'property',
  key: string,
  content: string | null,
) {
  const selector = `meta[${attribute}="${key}"]`
  const meta = document.querySelector<HTMLMetaElement>(selector)
  if (!content) {
    meta?.remove()
    return
  }

  const element = meta ?? document.createElement('meta')
  element.setAttribute(attribute, key)
  element.content = content
  if (!meta) {
    document.head.append(element)
  }
}
