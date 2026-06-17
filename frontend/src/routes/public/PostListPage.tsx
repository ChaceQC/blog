import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { ListPager } from '../../components/ListPager.tsx'
import { PostList } from '../../features/posts/PostList.tsx'
import {
  listPublicCategories,
  listPublicPosts,
  listPublicTags,
} from '../../features/posts/api.ts'
import type { PublicTaxonomyItem } from '../../features/posts/types.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'

const PAGE_SIZE = 5
const pageDescription = '按发布时间收起已经公开的文章和随手记下的长句。'

export function PostListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parsePage(searchParams.get('page'))
  const categorySlug = searchParams.get('category') ?? undefined
  const tagSlug = searchParams.get('tag') ?? undefined

  const categoriesQuery = useQuery({
    queryKey: ['public-categories', 'archive'],
    queryFn: () => listPublicCategories({ limit: 50 }),
  })
  const tagsQuery = useQuery({
    queryKey: ['public-tags', 'archive'],
    queryFn: () => listPublicTags({ limit: 50 }),
  })
  const { data, isError, isLoading } = useQuery({
    queryKey: ['public-posts', 'archive', page, categorySlug, tagSlug],
    queryFn: () =>
      listPublicPosts({
        limit: PAGE_SIZE + 1,
        offset: page * PAGE_SIZE,
        categorySlug,
        tagSlug,
      }),
  })
  const posts = (data?.items ?? []).slice(0, PAGE_SIZE)
  const hasNextPage = (data?.items.length ?? 0) > PAGE_SIZE
  const categories = categoriesQuery.data?.items ?? []
  const tags = tagsQuery.data?.items ?? []
  const activeCategory = categories.find((item) => item.slug === categorySlug)
  const activeTag = tags.find((item) => item.slug === tagSlug)
  const activeFilterLabel = filterLabel(activeCategory, activeTag)
  const seoPath = `/posts${searchParams.toString() ? `?${searchParams.toString()}` : ''}`

  usePageSeo({
    title: activeFilterLabel === '全部文章' ? '全部文章' : `${activeFilterLabel}文章`,
    description: pageDescription,
    path: seoPath,
    keywords: '文章,写作,博客',
  })

  function setPage(nextPage: number) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (nextPage <= 0) {
        next.delete('page')
      } else {
        next.set('page', String(nextPage + 1))
      }
      return next
    })
  }

  function toggleFilter(kind: 'category' | 'tag', slug: string) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (next.get(kind) === slug) {
        next.delete(kind)
      } else {
        next.set(kind, slug)
      }
      next.delete('page')
      return next
    })
  }

  function clearFilter(kind: 'category' | 'tag') {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.delete(kind)
      next.delete('page')
      return next
    })
  }

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>ARCHIVE</small>
        <h1>全部文章</h1>
        <p>{pageDescription}</p>
      </section>
      <section className="content-section">
        <div className="archive-filter-panel" aria-label="文章归档筛选">
          <div className="section-heading section-heading--stacked">
            <small>FILTER</small>
            <span>归档筛选</span>
            <small>{activeFilterLabel}</small>
          </div>
          <TaxonomyFilterGroup
            activeSlug={categorySlug}
            allLabel="全部分类"
            isLoading={categoriesQuery.isLoading}
            items={categories}
            label="分类"
            onClear={() => clearFilter('category')}
            onToggle={(slug) => toggleFilter('category', slug)}
          />
          <TaxonomyFilterGroup
            activeSlug={tagSlug}
            allLabel="全部标签"
            isLoading={tagsQuery.isLoading}
            items={tags}
            label="标签"
            onClear={() => clearFilter('tag')}
            onToggle={(slug) => toggleFilter('tag', slug)}
          />
          {categoriesQuery.isError || tagsQuery.isError ? (
            <p className="empty-state">分类或标签暂时不可用。</p>
          ) : null}
        </div>
        <div className="section-heading section-heading--stacked">
          <small>WRITING</small>
          <span>文稿</span>
          <small>{isLoading ? '加载中' : `第 ${page + 1} 页`}</small>
        </div>
        {isError ? <p className="empty-state">文章服务暂时不可用。</p> : null}
        {!isLoading && !isError && posts.length === 0 ? (
          <p className="empty-state">
            {activeFilterLabel === '全部文章'
              ? '还没有公开发布的文章。'
              : '没有找到符合筛选条件的文章。'}
          </p>
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

type TaxonomyFilterGroupProps = {
  activeSlug: string | undefined
  allLabel: string
  isLoading: boolean
  items: PublicTaxonomyItem[]
  label: string
  onClear: () => void
  onToggle: (slug: string) => void
}

function TaxonomyFilterGroup({
  activeSlug,
  allLabel,
  isLoading,
  items,
  label,
  onClear,
  onToggle,
}: TaxonomyFilterGroupProps) {
  return (
    <div className="archive-filter-group">
      <span>{label}</span>
      <div className="archive-filter-options">
        <button
          className={activeSlug ? 'archive-filter-chip' : 'archive-filter-chip is-active'}
          disabled={isLoading}
          onClick={onClear}
          type="button"
        >
          {allLabel}
        </button>
        {items.map((item) => (
          <button
            className={
              item.slug === activeSlug
                ? 'archive-filter-chip is-active'
                : 'archive-filter-chip'
            }
            disabled={isLoading}
            key={item.id}
            onClick={() => onToggle(item.slug)}
            type="button"
          >
            {item.name}
            <small>{item.post_count}</small>
          </button>
        ))}
      </div>
    </div>
  )
}

function parsePage(value: string | null) {
  const page = Number.parseInt(value ?? '1', 10)
  if (Number.isNaN(page) || page < 1) {
    return 0
  }
  return page - 1
}

function filterLabel(
  category: PublicTaxonomyItem | undefined,
  tag: PublicTaxonomyItem | undefined,
) {
  if (category && tag) {
    return `${category.name} / #${tag.name}`
  }
  if (category) {
    return category.name
  }
  if (tag) {
    return `#${tag.name}`
  }
  return '全部文章'
}
