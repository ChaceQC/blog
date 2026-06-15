import { SiteGrid } from '../../features/sites/SiteGrid.tsx'
import { sampleSites } from '../../features/sites/sampleSites.ts'

export function SitesPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="content-section">
        <div className="section-heading">
          <span>站点目录</span>
          <small>{sampleSites.length} 个入口</small>
        </div>
        <SiteGrid sites={sampleSites} />
      </section>
    </div>
  )
}
