import type { AuthUser } from './types.ts'

const WILDCARD_PERMISSION = '*'

export function hasAdminPermission(
  user: AuthUser,
  permission: string,
): boolean {
  return (
    user.permissions.includes(WILDCARD_PERMISSION) ||
    user.permissions.includes(permission)
  )
}

export function hasAnyAdminPermission(
  user: AuthUser,
  permissions: readonly string[],
): boolean {
  if (permissions.length === 0) {
    return true
  }

  return permissions.some((permission) => hasAdminPermission(user, permission))
}
