import { PostList } from '../../features/posts/PostList.tsx'
import { samplePosts } from '../../features/posts/samplePosts.ts'

export function PostListPage() {
  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>ARCHIVE</small>
        <h1>全部文章</h1>
        <p>按发布时间收束草稿、技术记录和长期维护的发布流程。</p>
      </section>
      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>WRITING</small>
          <span>文稿</span>
          <small>{samplePosts.length} 篇</small>
        </div>
        <PostList posts={samplePosts} />
      </section>
    </div>
  )
}
