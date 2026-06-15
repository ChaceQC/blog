import { Clock3 } from 'lucide-react'

import { StatusBadge } from '../../components/StatusBadge.tsx'
import type { PostSummary } from './samplePosts.ts'

const statusLabels = {
  draft: '草稿',
  published: '已发布',
} satisfies Record<PostSummary['status'], string>

type PostListProps = {
  posts: PostSummary[]
}

export function PostList({ posts }: PostListProps) {
  return (
    <div className="post-list">
      {posts.map((post) => (
        <article className="post-row" key={post.id}>
          <img className="post-row__image" src={post.coverUrl} alt="" />
          <div className="post-row__body">
            <div className="post-row__meta">
              <StatusBadge tone={post.status}>{statusLabels[post.status]}</StatusBadge>
              <span>{post.category}</span>
            </div>
            <h2>{post.title}</h2>
            <p>{post.summary}</p>
            <div className="post-row__footer">
              <span>{post.publishedAt}</span>
              <span>
                <Clock3 size={16} strokeWidth={1.8} aria-hidden="true" />
                {post.readingMinutes} 分钟
              </span>
            </div>
          </div>
        </article>
      ))}
    </div>
  )
}
