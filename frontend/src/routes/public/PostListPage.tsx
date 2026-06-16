import { useQuery } from '@tanstack/react-query'

import { PostList } from '../../features/posts/PostList.tsx'
import { listPublicPosts } from '../../features/posts/api.ts'

export function PostListPage() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['public-posts', 'archive'],
    queryFn: () => listPublicPosts({ limit: 50 }),
  })
  const posts = data?.items ?? []

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
          <small>{isLoading ? '加载中' : `${posts.length} 篇`}</small>
        </div>
        {isError ? <p className="empty-state">文章服务暂时不可用。</p> : null}
        {!isLoading && !isError && posts.length === 0 ? (
          <p className="empty-state">还没有公开发布的文章。</p>
        ) : null}
        {posts.length > 0 ? <PostList posts={posts} /> : null}
      </section>
    </div>
  )
}
