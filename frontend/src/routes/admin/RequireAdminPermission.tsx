import { type PropsWithChildren } from 'react'

import { hasAnyAdminPermission } from '../../features/auth/permissions.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

type RequireAdminPermissionProps = PropsWithChildren<{
  permissions: readonly string[]
}>

export function RequireAdminPermission({
  children,
  permissions,
}: RequireAdminPermissionProps) {
  const { session } = useAuth()

  if (
    session === null ||
    !hasAnyAdminPermission(session.user, permissions)
  ) {
    return (
      <section className="admin-forbidden">
        <span>权限不足</span>
        <h1>无法访问此后台模块</h1>
      </section>
    )
  }

  return children
}
