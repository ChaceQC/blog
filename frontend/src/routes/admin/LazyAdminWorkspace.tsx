import { lazy, Suspense } from 'react'

const AdminWorkspaceRoutes = lazy(() => import('./AdminWorkspaceRoutes.tsx'))

export function LazyAdminWorkspace() {
  return (
    <Suspense fallback={<main className="admin-auth-loading">正在加载管理台</main>}>
      <AdminWorkspaceRoutes />
    </Suspense>
  )
}
