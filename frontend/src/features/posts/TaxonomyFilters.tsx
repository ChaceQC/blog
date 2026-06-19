import { MoreHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ListPager } from '../../components/ListPager.tsx'
import { usePagedItems } from '../../hooks/usePagedItems.ts'
import { compareTaxonomyItems } from './archiveHelpers.ts'
import type { PublicTaxonomyItem } from './types.ts'

const TAXONOMY_VISIBLE_LIMIT = 5
const TAXONOMY_MODAL_PAGE_SIZE = 12

type TaxonomyFilterGroupProps = {
  activeSlug: string | undefined
  allLabel: string
  isLoading: boolean
  items: PublicTaxonomyItem[]
  label: string
  linkPrefix: '/categories' | '/tags'
}

export function TaxonomyFilterGroup({
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
  const { safePage: currentModalPage, visibleItems: modalItems } = usePagedItems(
    hiddenItems,
    modalPage,
    TAXONOMY_MODAL_PAGE_SIZE,
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
