import { FriendLinkList } from '../../features/links/FriendLinkList.tsx'
import { sampleLinks } from '../../features/links/sampleLinks.ts'

export function LinksPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>FRIENDS</small>
        <h1>友链</h1>
        <p>保留一些值得长期互相拜访的站点，审核状态和描述后续由后台维护。</p>
      </section>
      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>BOOKMARKS</small>
          <span>朋友们</span>
          <small>{sampleLinks.length} 个站点</small>
        </div>
        <FriendLinkList links={sampleLinks} />
      </section>
    </div>
  )
}
