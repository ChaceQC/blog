import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { invalidatePageCaches } from '../../app/queryInvalidation.ts'
import {
  createAdminPage,
  deleteAdminPage,
  listAdminPages,
  updateAdminPage,
} from './api.ts'
import { usePagedItems } from '../../hooks/usePagedItems.ts'
import { nullableText } from '../../utils/formText.ts'

import type { AuthSession } from '../auth/session.ts'
import type {
  AdminPageItem,
  AdminPageListResponse,
  PageFormPayload,
} from './types.ts'

export const emptyPageForm: PageFormPayload = {
  title: '',
  slug: '',
  content_md: '',
  status: 'draft',
  show_in_nav: false,
  sort_order: 0,
  seo_title: '',
  seo_description: '',
}

const emptyPages: AdminPageItem[] = []
const LIST_PAGE_SIZE = 8

export function useAdminPageEditor(session: AuthSession | null) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | 'new'>('new')
  const [form, setForm] = useState<PageFormPayload>(emptyPageForm)
  const [notice, setNotice] = useState<string | null>(null)
  const [isPreviewOpen, setPreviewOpen] = useState(false)
  const [listPage, setListPage] = useState(0)

  const pagesQuery = useQuery({
    queryKey: ['admin-pages'],
    queryFn: listAdminPages,
  })
  const pages = pagesQuery.data?.items ?? emptyPages
  const { safePage: safeListPage, visibleItems: visiblePages } = usePagedItems(
    pages,
    listPage,
    LIST_PAGE_SIZE,
  )
  const selectedPage = useMemo(
    () => pages.find((page) => page.id === selectedId) ?? null,
    [pages, selectedId],
  )

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }

      const payload = normalizePageForm(form)
      if (selectedPage) {
        return updateAdminPage(selectedPage.id, payload, session.csrfToken)
      }
      return createAdminPage(payload, session.csrfToken)
    },
    onSuccess: (page) => {
      void invalidatePageCaches(queryClient)
      setSelectedId(page.id)
      setForm(pageToForm(page))
      setNotice('页面已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedPage) {
        throw new Error('当前页面无法删除')
      }
      return deleteAdminPage(selectedPage.id, session.csrfToken)
    },
    onSuccess: (page) => {
      queryClient.setQueryData<AdminPageListResponse>(
        ['admin-pages'],
        (current) => removePageListItem(current, page.id),
      )
      void invalidatePageCaches(queryClient)
      startNewPage()
      setNotice('页面已删除')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '删除失败')
    },
  })

  function selectPage(page: AdminPageItem) {
    setSelectedId(page.id)
    setForm(pageToForm(page))
    setPreviewOpen(false)
    setNotice(null)
  }

  function startNewPage() {
    setSelectedId('new')
    setForm(emptyPageForm)
    setPreviewOpen(false)
    setNotice(null)
  }

  function updateForm<Key extends keyof PageFormPayload>(
    key: Key,
    value: PageFormPayload[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  return {
    form,
    isError: pagesQuery.isError,
    isLoading: pagesQuery.isLoading,
    isPreviewOpen,
    listPageSize: LIST_PAGE_SIZE,
    notice,
    pages,
    safeListPage,
    deleteMutation,
    saveMutation,
    selectedPage,
    setListPage,
    setPreviewOpen,
    startNewPage,
    updateForm,
    visiblePages,
    selectPage,
  }
}

export function pageToForm(page: AdminPageItem): PageFormPayload {
  return {
    title: page.title,
    slug: page.slug,
    content_md: page.content_md,
    status: page.status,
    show_in_nav: page.show_in_nav,
    sort_order: page.sort_order,
    seo_title: page.seo_title ?? '',
    seo_description: page.seo_description ?? '',
  }
}

function normalizePageForm(form: PageFormPayload): PageFormPayload {
  return {
    ...form,
    seo_title: nullableText(form.seo_title),
    seo_description: nullableText(form.seo_description),
  }
}

function removePageListItem(
  current: AdminPageListResponse | undefined,
  pageId: number,
): AdminPageListResponse {
  if (!current) {
    return { items: [] }
  }
  return {
    ...current,
    items: current.items.filter((item) => item.id !== pageId),
  }
}
