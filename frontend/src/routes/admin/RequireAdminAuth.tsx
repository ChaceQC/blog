import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../../features/auth/useAuth.ts'

export function RequireAdminAuth() {
  const { session } = useAuth()
  const location = useLocation()

  if (session === null) {
    return (
      <Navigate
        to="/admin/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  return <Outlet />
}
