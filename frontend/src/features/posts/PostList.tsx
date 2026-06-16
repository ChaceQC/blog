import { Clock3 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { StatusBadge } from '../../components/StatusBadge.tsx'
import {
  formatPostDate,
  getReadingMinutes,
  postCoverUrl,
} from './postMeta.ts'
import type { PublicPostItem } from './types.ts'

type PostListProps = {
  posts: PublicPostItem[]
  startIndex?: number
}

export function PostList({ posts, startIndex = 0 }: PostListProps) {
  return (
    <div className="post-list">
      {posts.map((post, index) => (
        <article className="post-row" key={post.id}>
          <span className="post-row__index">
            {String(startIndex + index + 1).padStart(2, '0')}
          </span>
          <Link className="post-row__cover" to={`/posts/${post.slug}`}>
            <img
              alt={post.title}
              loading="lazy"
              src={postCoverUrl(post)}
            />
          </Link>
          <div className="post-row__body">
            <div className="post-row__meta">
              <StatusBadge tone="published">已发布</StatusBadge>
              <span>{post.category_names[0] ?? '文章'}</span>
            </div>
            <h2>
              <Link to={`/posts/${post.slug}`}>{post.title}</Link>
            </h2>
            <p>{post.summary ?? post.seo_description ?? '这篇文章暂时没有摘要。'}</p>
            {post.tag_names.length > 0 ? (
              <div className="post-taxonomy">
                {post.tag_names.slice(0, 4).map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
            ) : null}
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
