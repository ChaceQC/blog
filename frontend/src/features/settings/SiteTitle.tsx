import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { getPublicSiteProfile } from './api.ts'
import { siteSettings } from './siteSettings.ts'

export function SiteTitle() {
  const { data } = useQuery({
    queryKey: ['public-site-profile'],
    queryFn: getPublicSiteProfile,
  })
  const title = data?.title ?? siteSettings.title

  useEffect(() => {
    document.title = title
  }, [title])

  return null
}
