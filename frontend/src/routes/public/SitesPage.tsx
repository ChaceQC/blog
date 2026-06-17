import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { listPublicSiteItems } from '../../features/sites/api.ts'
import type { SiteItem } from '../../features/sites/types.ts'

const PAGE_SIZE = 9
const pageDescription = '把常用入口收在一页，需要的时候不用到处翻。'
const emptySites: SiteItem[] = []

export function SitesPage() {
  const [page, setPage] = useState(0)
  const {
    data: sitesData,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ['public-site-items'],
    queryFn: () => listPublicSiteItems({ limit: 100 }),
  })
  const sites = sitesData?.items ?? emptySites
  const safePage = Math.min(page, Math.max(0, Math.ceil(sites.length / PAGE_SIZE) - 1))
  const visibleSites = useMemo(
    () => sites.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE),
    [safePage, sites],
  )
  usePageSeo({
    title: '站点目录',
    description: pageDescription,
    path: '/sites',
    keywords: '站点目录,导航,工具入口',
  })

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>GATEWAYS</small>
        <h1>站点目录</h1>
        <p>{pageDescription}</p>
      </section>
      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>DIRECTORY</small>
          <span>入口</span>
          <small>{isLoading ? '加载中' : `${sites.length} 个入口`}</small>
        </div>
        {isError ? <p className="empty-state">站点目录暂时不可用。</p> : null}
        {!isLoading && !isError && sites.length === 0 ? (
          <p className="empty-state">还没有公开入口。</p>
        ) : null}
        <SiteGrid sites={visibleSites} />
        <ListPager
          page={safePage}
          pageSize={PAGE_SIZE}
          totalItems={sites.length}
          isLoading={isLoading}
          onPageChange={setPage}
        />
      </section>
    </div>
  )
}
