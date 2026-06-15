import { FriendLinkList } from '../../features/links/FriendLinkList.tsx'
import { sampleLinks } from '../../features/links/sampleLinks.ts'

export function LinksPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="content-section">
        <div className="section-heading">
          <span>友链</span>
          <small>{sampleLinks.length} 个站点</small>
        </div>
        <FriendLinkList links={sampleLinks} />
      </section>
    </div>
  )
}
