import { RouterProvider } from 'react-router-dom'

import { SiteTitle } from '../features/settings/SiteTitle.tsx'
import { router } from './router.tsx'

export default function App() {
  return (
    <>
      <SiteTitle />
      <RouterProvider router={router} />
    </>
  )
}
