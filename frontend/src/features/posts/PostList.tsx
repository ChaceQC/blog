import { Clock3 } from 'lucide-react'
import { Link } from 'react-router-dom'

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
      {posts.map((post, index) => (
        <article className="post-row" key={post.id}>
          <span className="post-row__index">
            {String(index + 1).padStart(2, '0')}
          </span>
          <div className="post-row__body">
            <div className="post-row__meta">
              <StatusBadge tone={post.status}>{statusLabels[post.status]}</StatusBadge>
              <span>{post.category}</span>
            </div>
            <h2>
              <Link to="/posts">{post.title}</Link>
            </h2>
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
