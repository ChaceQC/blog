import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { PostList } from '../../features/posts/PostList.tsx'
import { listPublicPosts } from '../../features/posts/api.ts'

const PAGE_SIZE = 5

export function PostListPage() {
  const [page, setPage] = useState(0)
  const { data, isError, isLoading } = useQuery({
    queryKey: ['public-posts', 'archive', page],
    queryFn: () =>
      listPublicPosts({ limit: PAGE_SIZE + 1, offset: page * PAGE_SIZE }),
  })
  const posts = (data?.items ?? []).slice(0, PAGE_SIZE)
  const hasNextPage = (data?.items.length ?? 0) > PAGE_SIZE

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>ARCHIVE</small>
        <h1>全部文章</h1>
        <p>按发布时间收起已经公开的文章和随手记下的长句。</p>
      </section>
      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>WRITING</small>
          <span>文稿</span>
          <small>{isLoading ? '加载中' : `第 ${page + 1} 页`}</small>
        </div>
        {isError ? <p className="empty-state">文章服务暂时不可用。</p> : null}
        {!isLoading && !isError && posts.length === 0 ? (
          <p className="empty-state">还没有公开发布的文章。</p>
        ) : null}
        {posts.length > 0 ? <PostList posts={posts} startIndex={page * PAGE_SIZE} /> : null}
        <ListPager
          page={page}
          pageSize={PAGE_SIZE}
          totalItems={page * PAGE_SIZE + posts.length + (hasNextPage ? 1 : 0)}
          isLoading={isLoading}
          onPageChange={setPage}
        />
      </section>
    </div>
  )
}
