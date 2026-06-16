import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { FriendLinkList } from '../../features/links/FriendLinkList.tsx'
import { listPublicFriendLinks } from '../../features/links/api.ts'
import type { FriendLink } from '../../features/links/types.ts'

const PAGE_SIZE = 8
const emptyLinks: FriendLink[] = []

export function LinksPage() {
  const [page, setPage] = useState(0)
  const {
    data: linksData,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ['public-friend-links'],
    queryFn: () => listPublicFriendLinks({ limit: 100 }),
  })
  const links = linksData?.items ?? emptyLinks
  const safePage = Math.min(page, Math.max(0, Math.ceil(links.length / PAGE_SIZE) - 1))
  const visibleLinks = useMemo(
    () => links.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE),
    [links, safePage],
  )

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
        <FriendLinkList links={visibleLinks} />
        <ListPager
          page={safePage}
          pageSize={PAGE_SIZE}
          totalItems={links.length}
          isLoading={isLoading}
          onPageChange={setPage}
        />
      </section>
    </div>
  )
}
