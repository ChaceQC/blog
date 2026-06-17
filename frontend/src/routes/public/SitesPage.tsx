import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { ListPager } from '../../components/ListPager.tsx'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'
import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { listPublicSiteItems } from '../../features/sites/api.ts'
import type { SiteItem } from '../../features/sites/types.ts'

const PAGE_SIZE = 6
const pageDescription = '把常用入口收在一页，需要的时候不用到处翻。'
const emptySites: SiteItem[] = []

export function SitesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parsePage(searchParams.get('page'))
  const {
    data: sitesData,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ['public-site-items', page],
    queryFn: () =>
      listPublicSiteItems({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  })
  const sites = sitesData?.items ?? emptySites
  const totalSites = sitesData?.total ?? 0
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
          <small>{isLoading ? '加载中' : `第 ${page + 1} 页`}</small>
        </div>
        {isError ? <p className="empty-state">站点目录暂时不可用。</p> : null}
        {!isLoading && !isError && totalSites === 0 ? (
          <p className="empty-state">还没有公开入口。</p>
        ) : null}
        <SiteGrid sites={sites} />
        <ListPager
          page={page}
          pageSize={PAGE_SIZE}
          totalItems={totalSites}
          isLoading={isLoading}
          onPageChange={setPage}
        />
      </section>
    </div>
  )

  function setPage(nextPage: number) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (nextPage <= 0) {
        next.delete('page')
      } else {
        next.set('page', String(nextPage + 1))
      }
      return next
    })
  }
}

function parsePage(value: string | null) {
  const page = Number.parseInt(value ?? '1', 10)
  if (Number.isNaN(page) || page < 1) {
    return 0
  }
  return page - 1
}
