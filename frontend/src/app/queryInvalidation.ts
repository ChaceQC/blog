import type { QueryClient, QueryKey } from '@tanstack/react-query'

export function invalidatePostCaches(queryClient: QueryClient): Promise<void> {
  return invalidateQueryGroups(queryClient, [
    ['admin-posts'],
    ['public-posts'],
    ['public-post'],
    ['public-categories'],
    ['public-tags'],
    ['public-category'],
    ['public-tag'],
  ])
}

export function invalidatePageCaches(queryClient: QueryClient): Promise<void> {
  return invalidateQueryGroups(queryClient, [
    ['admin-pages'],
    ['public-page'],
  ])
}

export function invalidateFileCaches(queryClient: QueryClient): Promise<void> {
  return invalidateQueryGroups(queryClient, [
    ['admin-files'],
    ['public-files'],
  ])
}

export function invalidateFriendLinkCaches(
  queryClient: QueryClient,
): Promise<void> {
  return invalidateQueryGroups(queryClient, [
    ['admin-friend-link-groups'],
    ['admin-friend-links'],
    ['public-friend-links'],
  ])
}

export function invalidateSiteNavCaches(
  queryClient: QueryClient,
): Promise<void> {
  return invalidateQueryGroups(queryClient, [
    ['admin-site-nav-groups'],
    ['admin-site-nav-items'],
    ['public-site-items'],
  ])
}

export function invalidateSiteProfileCaches(
  queryClient: QueryClient,
): Promise<void> {
  return invalidateQueryGroups(queryClient, [
    ['admin-settings'],
    ['public-site-profile'],
  ])
}

function invalidateQueryGroups(
  queryClient: QueryClient,
  queryKeys: QueryKey[],
): Promise<void> {
  return Promise.all(
    queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  ).then(() => undefined)
}
