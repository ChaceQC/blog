import { Clock3 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { StatusBadge } from '../../components/StatusBadge.tsx'
import { formatPostDate, getReadingMinutes } from './postMeta.ts'
import type { PublicPostItem } from './types.ts'

type PostListProps = {
  posts: PublicPostItem[]
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
              <StatusBadge tone="published">已发布</StatusBadge>
              <span>文章</span>
            </div>
            <h2>
              <Link to={`/posts/${post.slug}`}>{post.title}</Link>
            </h2>
            <p>{post.summary ?? post.seo_description ?? '这篇文章暂时没有摘要。'}</p>
            <div className="post-row__footer">
              <span>{formatPostDate(post.published_at)}</span>
              <span>
                <Clock3 size={16} strokeWidth={1.8} aria-hidden="true" />
                {getReadingMinutes(post.word_count)} 分钟
              </span>
            </div>
          </div>
        </article>
      ))}
    </div>
  )
}
