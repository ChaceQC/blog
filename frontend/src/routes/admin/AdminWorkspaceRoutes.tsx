import { useRoutes } from 'react-router-dom'

import { AdminDashboardPage } from './AdminDashboardPage.tsx'
import { AdminFilesPage } from './AdminFilesPage.tsx'
import { AdminLayout } from './AdminLayout.tsx'
import { AdminLinksPage } from './AdminLinksPage.tsx'
import { AdminLogsPage } from './AdminLogsPage.tsx'
import { AdminPagesPage } from './AdminPagesPage.tsx'
import { AdminPostsPage } from './AdminPostsPage.tsx'
import { AdminSettingsPage } from './AdminSettingsPage.tsx'
import { AdminSiteNavPage } from './AdminSiteNavPage.tsx'
import { adminAccess } from './adminAccess.ts'
import { RequireAdminPermission } from './RequireAdminPermission.tsx'

const adminWorkspaceRoutes = [
  {
    element: <AdminLayout />,
    children: [
      { index: true, element: <AdminDashboardPage /> },
      {
        path: 'posts',
        element: (
          <RequireAdminPermission permissions={adminAccess.posts}>
            <AdminPostsPage />
          </RequireAdminPermission>
        ),
      },
      {
        path: 'pages',
        element: (
          <RequireAdminPermission permissions={adminAccess.pages}>
            <AdminPagesPage />
          </RequireAdminPermission>
        ),
      },
      {
        path: 'files',
        element: (
          <RequireAdminPermission permissions={adminAccess.files}>
            <AdminFilesPage />
          </RequireAdminPermission>
        ),
      },
      {
        path: 'links',
        element: (
          <RequireAdminPermission permissions={adminAccess.links}>
            <AdminLinksPage />
          </RequireAdminPermission>
        ),
      },
      {
        path: 'site-nav',
        element: (
          <RequireAdminPermission permissions={adminAccess.siteNav}>
            <AdminSiteNavPage />
          </RequireAdminPermission>
        ),
      },
      {
        path: 'logs',
        element: (
          <RequireAdminPermission permissions={adminAccess.logs}>
            <AdminLogsPage />
          </RequireAdminPermission>
        ),
      },
      {
        path: 'settings',
        element: (
          <RequireAdminPermission permissions={adminAccess.settings}>
            <AdminSettingsPage />
          </RequireAdminPermission>
        ),
      },
    ],
  },
]

export default function AdminWorkspaceRoutes() {
  return useRoutes(adminWorkspaceRoutes)
}
