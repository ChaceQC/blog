import { useQuery } from '@tanstack/react-query'

import { FriendLinkList } from '../../features/links/FriendLinkList.tsx'
import { listPublicFriendLinks } from '../../features/links/api.ts'

export function LinksPage() {
  const {
    data: linksData,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ['public-friend-links'],
    queryFn: () => listPublicFriendLinks({ limit: 100 }),
  })
  const links = linksData?.items ?? []

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
          <small>{isLoading ? '加载中' : `${links.length} 个站点`}</small>
        </div>
        {isError ? <p className="empty-state">友链暂时不可用。</p> : null}
        {!isLoading && !isError && links.length === 0 ? (
          <p className="empty-state">还没有公开友链。</p>
        ) : null}
        <FriendLinkList links={links} />
      </section>
    </div>
  )
}
