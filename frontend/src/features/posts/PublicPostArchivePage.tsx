import { useQuery } from '@tanstack/react-query'
import { MoreHorizontal, X } from 'lucide-react'
import { useState } from 'react'
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
const TAXONOMY_VISIBLE_LIMIT = 5
const TAXONOMY_MODAL_PAGE_SIZE = 12
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
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalPage, setModalPage] = useState(0)
  const sortedItems = [...items].sort(compareTaxonomyItems)
  const visibleItems = sortedItems.slice(0, TAXONOMY_VISIBLE_LIMIT)
  const hiddenItems = sortedItems.slice(TAXONOMY_VISIBLE_LIMIT)
  const modalTotalPages = Math.max(
    1,
    Math.ceil(hiddenItems.length / TAXONOMY_MODAL_PAGE_SIZE),
  )
  const currentModalPage = Math.min(modalPage, modalTotalPages - 1)
  const modalItems = hiddenItems.slice(
    currentModalPage * TAXONOMY_MODAL_PAGE_SIZE,
    currentModalPage * TAXONOMY_MODAL_PAGE_SIZE + TAXONOMY_MODAL_PAGE_SIZE,
  )
  const hiddenActive = hiddenItems.some((item) => item.slug === activeSlug)

  function openModal() {
    setModalPage(0)
    setIsModalOpen(true)
  }

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
        {visibleItems.map((item) => (
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
        {hiddenItems.length > 0 ? (
          <button
            aria-label={`查看更多${label}`}
            className={
              hiddenActive
                ? 'archive-filter-chip archive-filter-more is-active'
                : 'archive-filter-chip archive-filter-more'
            }
            disabled={isLoading}
            onClick={openModal}
            type="button"
          >
            <MoreHorizontal size={16} strokeWidth={1.8} aria-hidden="true" />
            ...
            <small>{hiddenItems.length}</small>
          </button>
        ) : null}
      </div>
      {isModalOpen ? (
        <TaxonomyModal
          activeSlug={activeSlug}
          items={modalItems}
          label={label}
          linkPrefix={linkPrefix}
          onClose={() => setIsModalOpen(false)}
          page={currentModalPage}
          pageSize={TAXONOMY_MODAL_PAGE_SIZE}
          setPage={setModalPage}
          totalItems={hiddenItems.length}
        />
      ) : null}
    </div>
  )
}

type TaxonomyModalProps = {
  activeSlug: string | undefined
  items: PublicTaxonomyItem[]
  label: string
  linkPrefix: '/categories' | '/tags'
  onClose: () => void
  page: number
  pageSize: number
  setPage: (page: number) => void
  totalItems: number
}

function TaxonomyModal({
  activeSlug,
  items,
  label,
  linkPrefix,
  onClose,
  page,
  pageSize,
  setPage,
  totalItems,
}: TaxonomyModalProps) {
  return (
    <div className="taxonomy-modal-overlay" role="presentation">
      <div
        aria-labelledby={`taxonomy-modal-${label}`}
        aria-modal="true"
        className="taxonomy-modal"
        role="dialog"
      >
        <div className="taxonomy-modal__header">
          <div>
            <small>MORE</small>
            <h2 id={`taxonomy-modal-${label}`}>更多{label}</h2>
          </div>
          <button
            aria-label="关闭"
            className="icon-button taxonomy-modal__close"
            onClick={onClose}
            type="button"
          >
            <X size={18} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>
        <div className="taxonomy-modal__grid">
          {items.map((item) => (
            <Link
              className={
                item.slug === activeSlug
                  ? 'archive-filter-chip taxonomy-modal__chip is-active'
                  : 'archive-filter-chip taxonomy-modal__chip'
              }
              key={item.id}
              onClick={onClose}
              to={`${linkPrefix}/${item.slug}`}
            >
              {item.name}
              <small>{item.post_count}</small>
            </Link>
          ))}
        </div>
        <ListPager
          page={page}
          pageSize={pageSize}
          totalItems={totalItems}
          variant="admin"
          onPageChange={setPage}
        />
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

function compareTaxonomyItems(
  left: PublicTaxonomyItem,
  right: PublicTaxonomyItem,
) {
  if (right.post_count !== left.post_count) {
    return right.post_count - left.post_count
  }
  return left.name.localeCompare(right.name, 'zh-Hans-CN')
}
