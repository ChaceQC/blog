import type { PublicTaxonomyItem } from './types.ts'

export const pageDescription = '按发布时间收起已经公开的文章和随手记下的长句。'

export type TaxonomyScope = {
  kind: 'category' | 'tag'
  slug: string
}

export function filterLabel(
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

export function archiveHeading(
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

export function archiveSeoPath(
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

export function compareTaxonomyItems(
  left: PublicTaxonomyItem,
  right: PublicTaxonomyItem,
) {
  if (right.post_count !== left.post_count) {
    return right.post_count - left.post_count
  }
  return left.name.localeCompare(right.name, 'zh-Hans-CN')
}
