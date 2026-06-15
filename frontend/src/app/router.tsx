import { createBrowserRouter } from 'react-router-dom'

import { AdminDashboardPage } from '../routes/admin/AdminDashboardPage.tsx'
import { AdminLayout } from '../routes/admin/AdminLayout.tsx'
import { AdminLoginPage } from '../routes/admin/AdminLoginPage.tsx'
import { adminAccess } from '../routes/admin/adminAccess.ts'
import { RequireAdminAuth } from '../routes/admin/RequireAdminAuth.tsx'
import { RequireAdminPermission } from '../routes/admin/RequireAdminPermission.tsx'
import { HomePage } from '../routes/public/HomePage.tsx'
import { LinksPage } from '../routes/public/LinksPage.tsx'
import { PostListPage } from '../routes/public/PostListPage.tsx'
import { PublicLayout } from '../routes/public/PublicLayout.tsx'
import { SitesPage } from '../routes/public/SitesPage.tsx'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'posts', element: <PostListPage /> },
      { path: 'links', element: <LinksPage /> },
      { path: 'sites', element: <SitesPage /> },
    ],
  },
  {
    path: '/admin/login',
    element: <AdminLoginPage />,
  },
  {
    element: <RequireAdminAuth />,
    children: [
      {
        path: '/admin',
        element: <AdminLayout />,
        children: [
          { index: true, element: <AdminDashboardPage /> },
          {
            path: 'files',
            element: (
              <RequireAdminPermission permissions={adminAccess.files}>
                <AdminDashboardPage />
              </RequireAdminPermission>
            ),
          },
          {
            path: 'links',
            element: (
              <RequireAdminPermission permissions={adminAccess.links}>
                <AdminDashboardPage />
              </RequireAdminPermission>
            ),
          },
          {
            path: 'settings',
            element: (
              <RequireAdminPermission permissions={adminAccess.settings}>
                <AdminDashboardPage />
              </RequireAdminPermission>
            ),
          },
        ],
      },
    ],
  },
])
