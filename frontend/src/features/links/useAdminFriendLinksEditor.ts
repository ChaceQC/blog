import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { invalidateFriendLinkCaches } from '../../app/queryInvalidation.ts'
import { usePagedItems } from '../../hooks/usePagedItems.ts'
import {
  createAdminFriendLink,
  deleteAdminFriendLink,
  listAdminFriendLinkGroups,
  listAdminFriendLinks,
  reviewAdminFriendLink,
  updateAdminFriendLink,
} from './adminApi.ts'
import {
  emptyFriendLinkForm,
  formToPayload,
  linkToForm,
} from './friendLinkForm.ts'

import type { AuthSession } from '../auth/session.ts'
import type {
  AdminFriendLink,
  AdminFriendLinkListResponse,
  AdminFriendLinkStatus,
} from './types.ts'
import type { FriendLinkForm } from './friendLinkForm.ts'

const LIST_PAGE_SIZE = 8

export type ReviewedFriendLinkStatus = Exclude<
  AdminFriendLinkStatus,
  'pending'
>

export function useAdminFriendLinksEditor(session: AuthSession | null) {
  const queryClient = useQueryClient()
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null)
  const [draftForm, setDraftForm] = useState<FriendLinkForm | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [listPage, setListPage] = useState(0)
  const linksQuery = useQuery({
    queryKey: ['admin-friend-links'],
    queryFn: listAdminFriendLinks,
  })
  const groupsQuery = useQuery({
    queryKey: ['admin-friend-link-groups'],
    queryFn: listAdminFriendLinkGroups,
  })
  const links = useMemo(() => linksQuery.data?.items ?? [], [linksQuery.data])
  const groups = useMemo(() => groupsQuery.data?.items ?? [], [groupsQuery.data])
  const { safePage: safeListPage, visibleItems: visibleLinks } = usePagedItems(
    links,
    listPage,
    LIST_PAGE_SIZE,
  )
  const selectedLink = useMemo(
    () =>
      links.find((link) => link.id === selectedLinkId) ?? links[0] ?? null,
    [links, selectedLinkId],
  )
  const loadedForm = useMemo(
    () => (selectedLink ? linkToForm(selectedLink) : emptyFriendLinkForm),
    [selectedLink],
  )
  const savedForm = selectedLink ? loadedForm : null
  const form = draftForm ?? loadedForm
  const isCreating = selectedLinkId === null && draftForm !== null
  const hasUnsavedChanges =
    savedForm === null ||
    friendLinkFormSignature(form) !== friendLinkFormSignature(savedForm)
  const isPendingReview = Boolean(
    !isCreating && selectedLink && selectedLink.status === 'pending',
  )
  const isReviewedLink = Boolean(
    !isCreating && selectedLink && selectedLink.status !== 'pending',
  )
  const canSaveForm = Boolean(session) && form.name.trim() !== ''

  const reviewAndSaveMutation = useMutation({
    mutationFn: async (status: ReviewedFriendLinkStatus) => {
      if (!session || !selectedLink) {
        throw new Error('当前会话已失效')
      }
      await updateAdminFriendLink(
        selectedLink.id,
        formToPayload({ ...form, status }),
        session.csrfToken,
      )
      return reviewAdminFriendLink(selectedLink.id, { status }, session.csrfToken)
    },
    onSuccess: (link) => {
      queryClient.setQueryData<AdminFriendLinkListResponse>(
        ['admin-friend-links'],
        (current) => upsertFriendLinkListItem(current, link),
      )
      setSelectedLinkId(link.id)
      setDraftForm(null)
      void invalidateFriendLinkCaches(queryClient)
      setNotice('友链已审核并保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '审核保存失败')
    },
  })
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!session) {
        throw new Error('当前会话已失效')
      }
      const payload = formToPayload(form)
      if (isCreating || !selectedLink) {
        return createAdminFriendLink(payload, session.csrfToken)
      }
      return updateAdminFriendLink(selectedLink.id, payload, session.csrfToken)
    },
    onSuccess: (link) => {
      queryClient.setQueryData<AdminFriendLinkListResponse>(
        ['admin-friend-links'],
        (current) => upsertFriendLinkListItem(current, link),
      )
      setSelectedLinkId(link.id)
      setDraftForm(null)
      void invalidateFriendLinkCaches(queryClient)
      setNotice(isCreating ? '友链已创建' : '友链已保存')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '保存失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!session || !selectedLink || isCreating) {
        throw new Error('当前友链无法删除')
      }
      return deleteAdminFriendLink(selectedLink.id, session.csrfToken)
    },
    onSuccess: (link) => {
      queryClient.setQueryData<AdminFriendLinkListResponse>(
        ['admin-friend-links'],
        (current) => removeFriendLinkListItem(current, link.id),
      )
      setSelectedLinkId(null)
      setDraftForm(null)
      void invalidateFriendLinkCaches(queryClient)
      setNotice('友链已删除')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '删除失败')
    },
  })

  function startCreating() {
    setSelectedLinkId(null)
    setDraftForm(emptyFriendLinkForm)
    setNotice('正在新建友链')
  }

  function selectLink(link: AdminFriendLink) {
    setSelectedLinkId(link.id)
    setDraftForm(null)
    setNotice(null)
  }

  function updateForm<Key extends keyof FriendLinkForm>(
    key: Key,
    value: FriendLinkForm[Key],
  ) {
    setDraftForm((current) => ({ ...(current ?? form), [key]: value }))
  }

  return {
    canSaveForm,
    form,
    groups,
    groupsQuery,
    hasUnsavedChanges,
    isCreating,
    isPendingReview,
    isReviewedLink,
    links,
    linksQuery,
    listPageSize: LIST_PAGE_SIZE,
    notice,
    deleteMutation,
    reviewAndSaveMutation,
    safeListPage,
    saveMutation,
    selectLink,
    selectedLink,
    setListPage,
    startCreating,
    updateForm,
    visibleLinks,
  }
}

function friendLinkFormSignature(form: FriendLinkForm): string {
  return JSON.stringify(form)
}

function upsertFriendLinkListItem(
  current: AdminFriendLinkListResponse | undefined,
  link: AdminFriendLink,
): AdminFriendLinkListResponse {
  if (!current) {
    return { items: [link] }
  }
  const existingIndex = current.items.findIndex((item) => item.id === link.id)
  if (existingIndex === -1) {
    return { ...current, items: [link, ...current.items] }
  }
  return {
    ...current,
    items: current.items.map((item) => (item.id === link.id ? link : item)),
  }
}

function removeFriendLinkListItem(
  current: AdminFriendLinkListResponse | undefined,
  linkId: number,
): AdminFriendLinkListResponse {
  if (!current) {
    return { items: [] }
  }
  return {
    ...current,
    items: current.items.filter((item) => item.id !== linkId),
  }
}
