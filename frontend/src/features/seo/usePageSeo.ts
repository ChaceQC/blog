import { useEffect } from 'react'

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
  siteName = siteSettings.title,
  type = 'website',
}: PageSeoOptions) {
  useEffect(() => {
    const fullTitle = title === siteName ? title : `${title} | ${siteName}`
    const canonicalUrl = absoluteUrl(path)
    const absoluteImageUrl = imageUrl ? absoluteUrl(imageUrl) : null

    document.title = fullTitle
    setMeta('name', 'description', description)
    setMeta('name', 'keywords', keywords ?? null)
    setCanonical(canonicalUrl)
    setMeta('property', 'og:site_name', siteName)
    setMeta('property', 'og:type', type)
    setMeta('property', 'og:title', title)
    setMeta('property', 'og:description', description)
    setMeta('property', 'og:url', canonicalUrl)
    setMeta('property', 'og:image', absoluteImageUrl)
  }, [description, imageUrl, keywords, path, siteName, title, type])
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
