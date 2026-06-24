import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { invalidateSiteNavCaches } from '../../app/queryInvalidation.ts'
import { usePagedItems } from '../../hooks/usePagedItems.ts'
import {
  createAdminSiteNavItem,
  deleteAdminSiteNavItem,
  listAdminSiteNavGroups,
  listAdminSiteNavItems,
  updateAdminSiteNavItem,
} from './adminApi.ts'
import {
  emptySiteForm,
  siteFormToPayload,
  siteToForm,
} from './siteNavForm.ts'

import type { AuthSession } from '../auth/session.ts'
import type { AdminSiteNavItem, AdminSiteNavItemListResponse } from './types.ts'
import type { SiteNavForm } from './siteNavForm.ts'

const LIST_PAGE_SIZE = 6

export function useAdminSiteNavEditor(session: AuthSession | null) {
  const queryClient = useQueryClient()
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null)
  const [siteDraftForm, setSiteDraftForm] = useState<SiteNavForm | null>(null)
  const [siteNotice, setSiteNotice] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const sitesQuery = useQuery({
    queryKey: ['admin-site-nav-items'],
    queryFn: listAdminSiteNavItems,
  })
  const groupsQuery = useQuery({
    queryKey: ['admin-site-nav-groups'],
    queryFn: listAdminSiteNavGroups,
  })
  const sites = useMemo(() => sitesQuery.data?.items ?? [], [sitesQuery.data])
  const groups = useMemo(() => groupsQuery.data?.items ?? [], [groupsQuery.data])
  const { safePage: safeListPage, visibleItems: visibleSites } = usePagedItems(
    sites,
    listPage,
    LIST_PAGE_SIZE,
  )
  const selectedSite = useMemo(
    () =>
      sites.find((site) => site.id === selectedSiteId) ?? sites[0] ?? null,
    [sites, selectedSiteId],
  )
  const loadedSiteForm = useMemo(
    () => (selectedSite ? siteToForm(selectedSite) : emptySiteForm),
    [selectedSite],
  )
  const siteForm = siteDraftForm ?? loadedSiteForm
  const isCreatingSite = selectedSiteId === null && siteDraftForm !== null
  const saveSiteMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      const payload = siteFormToPayload(siteForm)
      if (isCreatingSite || !selectedSite) {
        return createAdminSiteNavItem(payload, session.csrfToken)
      }
      return updateAdminSiteNavItem(selectedSite.id, payload, session.csrfToken)
    },
    onSuccess: (site) => {
      setSelectedSiteId(site.id)
      setSiteDraftForm(null)
      void invalidateSiteNavCaches(queryClient)
      setSiteNotice(isCreatingSite ? '导航已创建' : '导航已保存')
    },
    onError: (error) => {
      setSiteNotice(error instanceof Error ? error.message : '导航保存失败')
    },
  })

  const deleteSiteMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedSite || isCreatingSite) {
        throw new Error('当前导航无法删除')
      }
      return deleteAdminSiteNavItem(selectedSite.id, session.csrfToken)
    },
    onSuccess: (site) => {
      queryClient.setQueryData<AdminSiteNavItemListResponse>(
        ['admin-site-nav-items'],
        (current) => removeSiteNavListItem(current, site.id),
      )
      setSelectedSiteId(null)
      setSiteDraftForm(null)
      void invalidateSiteNavCaches(queryClient)
      setSiteNotice('导航已删除')
    },
    onError: (error) => {
      setSiteNotice(error instanceof Error ? error.message : '删除失败')
    },
  })

  function startCreatingSite() {
    setSelectedSiteId(null)
    setSiteDraftForm(emptySiteForm)
    setSiteNotice('正在新建导航')
  }

  function selectSite(site: AdminSiteNavItem) {
    setSelectedSiteId(site.id)
    setSiteDraftForm(null)
    setSiteNotice(null)
  }

  function updateSiteForm<Key extends keyof SiteNavForm>(
    key: Key,
    value: SiteNavForm[Key],
  ) {
    setSiteDraftForm((current) => ({ ...(current ?? siteForm), [key]: value }))
  }

  return {
    groups,
    groupsQuery,
    isCreatingSite,
    listPageSize: LIST_PAGE_SIZE,
    safeListPage,
    deleteSiteMutation,
    saveSiteMutation,
    selectSite,
    selectedSite,
    setListPage,
    siteForm,
    siteNotice,
    sites,
    sitesQuery,
    startCreatingSite,
    updateSiteForm,
    visibleSites,
  }
}

function removeSiteNavListItem(
  current: AdminSiteNavItemListResponse | undefined,
  siteId: number,
): AdminSiteNavItemListResponse {
  if (!current) {
    return { items: [] }
  }
  return {
    ...current,
    items: current.items.filter((item) => item.id !== siteId),
  }
}
