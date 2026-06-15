import { PostList } from '../../features/posts/PostList.tsx'
import { samplePosts } from '../../features/posts/samplePosts.ts'

export function PostListPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="content-section">
        <div className="section-heading">
          <span>全部文章</span>
          <small>{samplePosts.length} 篇</small>
        </div>
        <PostList posts={samplePosts} />
      </section>
    </div>
  )
}
