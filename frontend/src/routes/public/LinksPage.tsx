import { FriendLinkList } from '../../features/links/FriendLinkList.tsx'
import { sampleLinks } from '../../features/links/sampleLinks.ts'

export function LinksPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>FRIENDS</small>
        <h1>友链</h1>
        <p>保留一些值得常去看看的站点，也给彼此留一个入口。</p>
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
