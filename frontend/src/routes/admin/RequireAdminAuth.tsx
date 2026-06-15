import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../../features/auth/useAuth.ts'

export function RequireAdminAuth() {
  const { isChecking, session } = useAuth()
  const location = useLocation()

  if (isChecking) {
    return <main className="admin-auth-loading">正在校验登录状态</main>
  }

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
