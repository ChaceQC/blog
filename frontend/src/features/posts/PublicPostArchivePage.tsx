import { useQuery } from '@tanstack/react-query'

import { publicErrorMessage } from '../../api/client.ts'
import { ListPager } from '../../components/ListPager.tsx'
import { useQueryPage } from '../../hooks/useQueryPage.ts'
import { usePageSeo } from '../seo/usePageSeo.ts'
import {
  getPublicCategory,
  getPublicTag,
  listPublicCategories,
  listPublicPosts,
  listPublicTags,
} from './api.ts'
import {
  archiveHeading,
  archiveSeoPath,
  filterLabel,
  pageDescription,
  type TaxonomyScope,
} from './archiveHelpers.ts'
import { PostList } from './PostList.tsx'
import { TaxonomyFilterGroup } from './TaxonomyFilters.tsx'

const PAGE_SIZE = 5

type PublicPostArchivePageProps = {
  taxonomy?: TaxonomyScope
}

export function PublicPostArchivePage({ taxonomy }: PublicPostArchivePageProps) {
  const { page, searchParams, setPage } = useQueryPage()
  const queryCategorySlug = searchParams.get('category') ?? undefined
  const queryTagSlug = searchParams.get('tag') ?? undefined
  const categorySlug =
    taxonomy?.kind === 'category' ? taxonomy.slug : queryCategorySlug
  const tagSlug = taxonomy?.kind === 'tag' ? taxonomy.slug : queryTagSlug

  const categoriesQuery = useQuery({
    queryKey: ['public-categories', 'archive'],
    queryFn: ({ signal }) => listPublicCategories({ limit: 100, signal }),
  })
  const tagsQuery = useQuery({
    queryKey: ['public-tags', 'archive'],
    queryFn: ({ signal }) => listPublicTags({ limit: 100, signal }),
  })
  const categoryDetailQuery = useQuery({
    queryKey: ['public-category', categorySlug],
    queryFn: ({ signal }) => getPublicCategory(categorySlug ?? '', { signal }),
    enabled: taxonomy?.kind === 'category' && Boolean(categorySlug),
  })
  const tagDetailQuery = useQuery({
    queryKey: ['public-tag', tagSlug],
    queryFn: ({ signal }) => getPublicTag(tagSlug ?? '', { signal }),
    enabled: taxonomy?.kind === 'tag' && Boolean(tagSlug),
  })
  const postsQuery = useQuery({
    queryKey: ['public-posts', 'archive', page, categorySlug, tagSlug],
    queryFn: ({ signal }) =>
      listPublicPosts({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        categorySlug,
        tagSlug,
        signal,
      }),
  })

  const posts = postsQuery.data?.items ?? []
  const totalPosts = postsQuery.data?.total ?? 0
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
  const taxonomyErrorMessage = publicErrorMessage(
    categoriesQuery.error ?? tagsQuery.error,
    '分类或标签暂时不可用。',
  )
  const taxonomyDetailErrorMessage = publicErrorMessage(
    categoryDetailQuery.error ?? tagDetailQuery.error,
    '这个归档入口暂时不存在。',
  )
  const postsErrorMessage = publicErrorMessage(
    postsQuery.error,
    '文章服务暂时不可用。',
  )

  usePageSeo({
    title: heading.title,
    description: pageDescription,
    path: seoPath,
    keywords: '文章,写作,博客,分类,标签',
  })

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
            <p className="empty-state">{taxonomyErrorMessage}</p>
          ) : null}
        </div>
        <div className="section-heading section-heading--stacked">
          <small>WRITING</small>
          <span>文稿</span>
          <small>{postsQuery.isLoading ? '加载中' : `第 ${page + 1} 页`}</small>
        </div>
        {taxonomyMissing ? <p className="empty-state">{taxonomyDetailErrorMessage}</p> : null}
        {postsQuery.isError ? <p className="empty-state">{postsErrorMessage}</p> : null}
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
          totalItems={totalPosts}
          isLoading={postsQuery.isLoading}
          onPageChange={setPage}
        />
      </section>
    </div>
  )
}
