import { createBrowserRouter, Outlet } from 'react-router-dom'

import { AuthProvider } from '../features/auth/AuthContext.tsx'
import { AdminLoginPage } from '../routes/admin/AdminLoginPage.tsx'
import { LazyAdminWorkspace } from '../routes/admin/LazyAdminWorkspace.tsx'
import { RequireAdminAuth } from '../routes/admin/RequireAdminAuth.tsx'
import { FilesPage } from '../routes/public/FilesPage.tsx'
import { HomePage } from '../routes/public/HomePage.tsx'
import { LinksPage } from '../routes/public/LinksPage.tsx'
import { PageDetailPage } from '../routes/public/PageDetailPage.tsx'
import { PostDetailPage } from '../routes/public/PostDetailPage.tsx'
import { PostListPage } from '../routes/public/PostListPage.tsx'
import { PublicLayout } from '../routes/public/PublicLayout.tsx'
import { SitesPage } from '../routes/public/SitesPage.tsx'
import { TaxonomyPostListPage } from '../routes/public/TaxonomyPostListPage.tsx'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'posts', element: <PostListPage /> },
      { path: 'posts/:slug', element: <PostDetailPage /> },
      { path: 'categories/:slug', element: <TaxonomyPostListPage kind="category" /> },
      { path: 'tags/:slug', element: <TaxonomyPostListPage kind="tag" /> },
      { path: 'links', element: <LinksPage /> },
      { path: 'files', element: <FilesPage /> },
      { path: 'sites', element: <SitesPage /> },
      { path: ':slug', element: <PageDetailPage /> },
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
            path: '/admin/*',
            element: <LazyAdminWorkspace />,
          },
        ],
      },
    ],
  },
])
