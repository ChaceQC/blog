import { RouterProvider } from 'react-router-dom'

import { SelectionHighlight } from '../components/SelectionHighlight.tsx'
import { SiteTitle } from '../features/settings/SiteTitle.tsx'
import { router } from './router.tsx'

export default function App() {
  return (
    <>
      <SiteTitle />
      <SelectionHighlight />
      <RouterProvider router={router} />
    </>
  )
}
