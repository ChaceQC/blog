import { createBrowserRouter, Outlet } from 'react-router-dom'

import { AuthProvider } from '../features/auth/AuthContext.tsx'
import { AdminDashboardPage } from '../routes/admin/AdminDashboardPage.tsx'
import { AdminFilesPage } from '../routes/admin/AdminFilesPage.tsx'
import { AdminLayout } from '../routes/admin/AdminLayout.tsx'
import { AdminLinksPage } from '../routes/admin/AdminLinksPage.tsx'
import { AdminLoginPage } from '../routes/admin/AdminLoginPage.tsx'
import { AdminPagesPage } from '../routes/admin/AdminPagesPage.tsx'
import { AdminPostsPage } from '../routes/admin/AdminPostsPage.tsx'
import { AdminSettingsPage } from '../routes/admin/AdminSettingsPage.tsx'
import { adminAccess } from '../routes/admin/adminAccess.ts'
import { RequireAdminAuth } from '../routes/admin/RequireAdminAuth.tsx'
import { RequireAdminPermission } from '../routes/admin/RequireAdminPermission.tsx'
import { HomePage } from '../routes/public/HomePage.tsx'
import { LinksPage } from '../routes/public/LinksPage.tsx'
import { PostDetailPage } from '../routes/public/PostDetailPage.tsx'
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
      { path: 'posts/:slug', element: <PostDetailPage /> },
      { path: 'links', element: <LinksPage /> },
      { path: 'sites', element: <SitesPage /> },
    ],
  },
  {
    element: (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    ),
    children: [
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
                path: 'settings',
                element: (
                  <RequireAdminPermission permissions={adminAccess.settings}>
                    <AdminSettingsPage />
                  </RequireAdminPermission>
                ),
              },
            ],
          },
        ],
      },
    ],
  },
])
