import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { sampleSites } from '../../features/sites/sampleSites.ts'

export function SitesPage() {
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
          <small>{sampleSites.length} 个入口</small>
        </div>
        <SiteGrid sites={sampleSites} />
      </section>
    </div>
  )
}
