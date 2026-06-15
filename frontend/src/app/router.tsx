import { createBrowserRouter } from 'react-router-dom'

import { AdminDashboardPage } from '../routes/admin/AdminDashboardPage.tsx'
import { AdminLayout } from '../routes/admin/AdminLayout.tsx'
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
    path: '/admin',
    element: <AdminLayout />,
    children: [
      { index: true, element: <AdminDashboardPage /> },
      { path: 'files', element: <AdminDashboardPage /> },
      { path: 'links', element: <AdminDashboardPage /> },
      { path: 'settings', element: <AdminDashboardPage /> },
    ],
  },
])
