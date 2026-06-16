import { useQuery } from '@tanstack/react-query'

import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { listPublicSiteItems } from '../../features/sites/api.ts'

export function SitesPage() {
  const {
    data: sitesData,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ['public-site-items'],
    queryFn: () => listPublicSiteItems({ limit: 100 }),
  })
  const sites = sitesData?.items ?? []

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>GATEWAYS</small>
        <h1>站点目录</h1>
        <p>把常用入口收在一页，需要的时候不用到处翻。</p>
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
        <SiteGrid sites={sites} />
      </section>
    </div>
  )
}
