import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { ListPager } from '../../components/ListPager.tsx'
import { usePageSeo } from '../seo/usePageSeo.ts'
import {
  getPublicCategory,
  getPublicTag,
  listPublicCategories,
  listPublicPosts,
  listPublicTags,
} from './api.ts'
import { PostList } from './PostList.tsx'
import type { PublicTaxonomyItem } from './types.ts'

const PAGE_SIZE = 5
const pageDescription = '按发布时间收起已经公开的文章和随手记下的长句。'

type TaxonomyScope = {
  kind: 'category' | 'tag'
  slug: string
}

type PublicPostArchivePageProps = {
  taxonomy?: TaxonomyScope
}

export function PublicPostArchivePage({ taxonomy }: PublicPostArchivePageProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parsePage(searchParams.get('page'))
  const queryCategorySlug = searchParams.get('category') ?? undefined
  const queryTagSlug = searchParams.get('tag') ?? undefined
  const categorySlug =
    taxonomy?.kind === 'category' ? taxonomy.slug : queryCategorySlug
  const tagSlug = taxonomy?.kind === 'tag' ? taxonomy.slug : queryTagSlug

  const categoriesQuery = useQuery({
    queryKey: ['public-categories', 'archive'],
    queryFn: () => listPublicCategories({ limit: 100 }),
  })
  const tagsQuery = useQuery({
    queryKey: ['public-tags', 'archive'],
    queryFn: () => listPublicTags({ limit: 100 }),
  })
  const categoryDetailQuery = useQuery({
    queryKey: ['public-category', categorySlug],
    queryFn: () => getPublicCategory(categorySlug ?? ''),
    enabled: taxonomy?.kind === 'category' && Boolean(categorySlug),
  })
  const tagDetailQuery = useQuery({
    queryKey: ['public-tag', tagSlug],
    queryFn: () => getPublicTag(tagSlug ?? ''),
    enabled: taxonomy?.kind === 'tag' && Boolean(tagSlug),
  })
  const postsQuery = useQuery({
    queryKey: ['public-posts', 'archive', page, categorySlug, tagSlug],
    queryFn: () =>
      listPublicPosts({
        limit: PAGE_SIZE + 1,
        offset: page * PAGE_SIZE,
        categorySlug,
        tagSlug,
      }),
  })

  const posts = (postsQuery.data?.items ?? []).slice(0, PAGE_SIZE)
  const hasNextPage = (postsQuery.data?.items.length ?? 0) > PAGE_SIZE
  const categories = categoriesQuery.data?.items ?? []
  const tags = tagsQuery.data?.items ?? []
  const activeCategory =
    categoryDetailQuery.data ??
    categories.find((item) => item.slug === categorySlug)
  const activeTag =
    tagDetailQuery.data ?? tags.find((item) => item.slug === tagSlug)
  const activeFilterLabel = filterLabel(
    activeCategory,
    activeTag,
    categorySlug,
    tagSlug,
  )
  const heading = archiveHeading(taxonomy, activeFilterLabel)
  const seoPath = archiveSeoPath(taxonomy, searchParams)
  const taxonomyMissing =
    categoryDetailQuery.isError || tagDetailQuery.isError

  usePageSeo({
    title: heading.title,
    description: pageDescription,
    path: seoPath,
    keywords: '文章,写作,博客,分类,标签',
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

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>{heading.eyebrow}</small>
        <h1>{heading.title}</h1>
        <p>{heading.description}</p>
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
            linkPrefix="/categories"
          />
          <TaxonomyFilterGroup
            activeSlug={tagSlug}
            allLabel="全部标签"
            isLoading={tagsQuery.isLoading}
            items={tags}
            label="标签"
            linkPrefix="/tags"
          />
          {categoriesQuery.isError || tagsQuery.isError ? (
            <p className="empty-state">分类或标签暂时不可用。</p>
          ) : null}
        </div>
        <div className="section-heading section-heading--stacked">
          <small>WRITING</small>
          <span>文稿</span>
          <small>{postsQuery.isLoading ? '加载中' : `第 ${page + 1} 页`}</small>
        </div>
        {taxonomyMissing ? <p className="empty-state">这个归档入口暂时不存在。</p> : null}
        {postsQuery.isError ? <p className="empty-state">文章服务暂时不可用。</p> : null}
        {!postsQuery.isLoading && !postsQuery.isError && posts.length === 0 ? (
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
          isLoading={postsQuery.isLoading}
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
  linkPrefix: '/categories' | '/tags'
}

function TaxonomyFilterGroup({
  activeSlug,
  allLabel,
  isLoading,
  items,
  label,
  linkPrefix,
}: TaxonomyFilterGroupProps) {
  return (
    <div className="archive-filter-group">
      <span>{label}</span>
      <div className="archive-filter-options">
        <Link
          className={activeSlug ? 'archive-filter-chip' : 'archive-filter-chip is-active'}
          aria-disabled={isLoading}
          to="/posts"
        >
          {allLabel}
        </Link>
        {items.map((item) => (
          <Link
            className={
              item.slug === activeSlug
                ? 'archive-filter-chip is-active'
                : 'archive-filter-chip'
            }
            aria-disabled={isLoading}
            key={item.id}
            to={`${linkPrefix}/${item.slug}`}
          >
            {item.name}
            <small>{item.post_count}</small>
          </Link>
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
  categorySlug: string | undefined,
  tagSlug: string | undefined,
) {
  const categoryLabel = category?.name ?? categorySlug
  const tagLabel = tag?.name ?? tagSlug
  if (categoryLabel && tagLabel) {
    return `${categoryLabel} / #${tagLabel}`
  }
  if (categoryLabel) {
    return categoryLabel
  }
  if (tagLabel) {
    return `#${tagLabel}`
  }
  return '全部文章'
}

function archiveHeading(
  taxonomy: TaxonomyScope | undefined,
  activeFilterLabel: string,
) {
  if (taxonomy?.kind === 'category') {
    return {
      eyebrow: 'CATEGORY',
      title: `分类：${activeFilterLabel}`,
      description: '按分类归拢同一主题下已经公开的文章。',
    }
  }
  if (taxonomy?.kind === 'tag') {
    return {
      eyebrow: 'TAG',
      title: activeFilterLabel,
      description: '按标签串起散落在不同文章里的关键词。',
    }
  }
  return {
    eyebrow: 'ARCHIVE',
    title: '全部文章',
    description: pageDescription,
  }
}

function archiveSeoPath(
  taxonomy: TaxonomyScope | undefined,
  searchParams: URLSearchParams,
) {
  const query = searchParams.toString()
  const path =
    taxonomy === undefined
      ? '/posts'
      : `/${taxonomy.kind === 'category' ? 'categories' : 'tags'}/${taxonomy.slug}`
  return `${path}${query ? `?${query}` : ''}`
}
