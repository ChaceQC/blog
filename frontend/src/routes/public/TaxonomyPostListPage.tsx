import { Navigate, useParams } from 'react-router-dom'

import { PublicPostArchivePage } from '../../features/posts/PublicPostArchivePage.tsx'

type TaxonomyPostListPageProps = {
  kind: 'category' | 'tag'
}

export function TaxonomyPostListPage({ kind }: TaxonomyPostListPageProps) {
  const { slug } = useParams()

  if (!slug) {
    return <Navigate replace to="/posts" />
  }

  return <PublicPostArchivePage taxonomy={{ kind, slug }} />
}
