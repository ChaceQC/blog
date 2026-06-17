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

const HIDDEN_PUBLIC_TAXONOMY_LABELS = new Set(['定时发布'])

export function PostList({ posts, startIndex = 0 }: PostListProps) {
  return (
    <div className="post-list">
      {posts.map((post, index) => {
        const categories = publicTaxonomyLabels(post.category_names)
        const tags = publicTaxonomyLabels(post.tag_names)

        return (
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
                {categories.length > 0 ? (
                  <div className="post-categories" aria-label="分类">
                    {categories.slice(0, 2).map((category) => (
                      <span key={category}>{category}</span>
                    ))}
                  </div>
                ) : null}
              </div>
              <h2>
                <Link to={`/posts/${post.slug}`}>{post.title}</Link>
              </h2>
              <p>{post.summary ?? post.seo_description ?? '这篇文章暂时没有摘要。'}</p>
              {tags.length > 0 ? (
                <div className="post-taxonomy" aria-label="标签">
                  {tags.slice(0, 5).map((tag) => (
                    <span key={tag}>#{tag}</span>
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
        )
      })}
    </div>
  )
}

function publicTaxonomyLabels(labels: string[]) {
  return labels.filter((label) => !HIDDEN_PUBLIC_TAXONOMY_LABELS.has(label))
}
