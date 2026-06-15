import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { sampleSites } from '../../features/sites/sampleSites.ts'

export function SitesPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>GATEWAYS</small>
        <h1>站点目录</h1>
        <p>把自建服务、文档和写作入口收在一页，方便从博客跳转到日常工具。</p>
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
