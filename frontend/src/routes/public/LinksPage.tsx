import { useMutation, useQuery } from '@tanstack/react-query'
import { type FormEvent, useMemo, useState } from 'react'

import { ListPager } from '../../components/ListPager.tsx'
import { FriendLinkList } from '../../features/links/FriendLinkList.tsx'
import {
  listPublicFriendLinks,
  submitPublicFriendLinkApplication,
} from '../../features/links/api.ts'
import type { FriendLink } from '../../features/links/types.ts'
import { usePageSeo } from '../../features/seo/usePageSeo.ts'

const PAGE_SIZE = 8
const pageDescription = '保留一些值得常去看看的站点，也给彼此留一个入口。'
const emptyLinks: FriendLink[] = []
const emptyApplicationForm = {
  name: '',
  url: '',
  avatarUrl: '',
  description: '',
  rssUrl: '',
}

export function LinksPage() {
  const [page, setPage] = useState(0)
  const [applicationForm, setApplicationForm] = useState(emptyApplicationForm)
  const [applicationNotice, setApplicationNotice] = useState<string | null>(null)
  const {
    data: linksData,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ['public-friend-links'],
    queryFn: () => listPublicFriendLinks({ limit: 100 }),
  })
  const links = linksData?.items ?? emptyLinks
  const safePage = Math.min(page, Math.max(0, Math.ceil(links.length / PAGE_SIZE) - 1))
  const visibleLinks = useMemo(
    () => links.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE),
    [links, safePage],
  )
  const applicationMutation = useMutation({
    mutationFn: submitPublicFriendLinkApplication,
    onSuccess: () => {
      setApplicationForm(emptyApplicationForm)
      setApplicationNotice('申请已提交，审核通过后会显示在这里。')
    },
    onError: (error) => {
      setApplicationNotice(error instanceof Error ? error.message : '申请提交失败')
    },
  })
  usePageSeo({
    title: '友链',
    description: pageDescription,
    path: '/links',
    keywords: '友链,个人站点,博客',
  })

  return (
    <div className="page-flow page-flow--narrow">
      <section className="page-heading">
        <small>FRIENDS</small>
        <h1>友链</h1>
        <p>{pageDescription}</p>
      </section>
      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>BOOKMARKS</small>
          <span>朋友们</span>
          <small>{isLoading ? '加载中' : `${links.length} 个站点`}</small>
        </div>
        {isError ? <p className="empty-state">友链暂时不可用。</p> : null}
        {!isLoading && !isError && links.length === 0 ? (
          <p className="empty-state">还没有公开友链。</p>
        ) : null}
        <FriendLinkList links={visibleLinks} />
        <ListPager
          page={safePage}
          pageSize={PAGE_SIZE}
          totalItems={links.length}
          isLoading={isLoading}
          onPageChange={setPage}
        />
      </section>
      <section className="content-section">
        <div className="section-heading section-heading--stacked">
          <small>EXCHANGE</small>
          <span>交换友链</span>
          <small>{applicationNotice ?? '提交后进入后台审核'}</small>
        </div>
        <form className="public-application-form" onSubmit={handleSubmitApplication}>
          <label>
            <span>站点名称</span>
            <input
              required
              maxLength={100}
              value={applicationForm.name}
              onChange={(event) => updateApplicationForm('name', event.target.value)}
            />
          </label>
          <label>
            <span>站点 URL</span>
            <input
              required
              type="url"
              maxLength={1000}
              value={applicationForm.url}
              onChange={(event) => updateApplicationForm('url', event.target.value)}
            />
          </label>
          <label>
            <span>头像 URL</span>
            <input
              type="url"
              maxLength={1000}
              value={applicationForm.avatarUrl}
              onChange={(event) =>
                updateApplicationForm('avatarUrl', event.target.value)
              }
            />
          </label>
          <label>
            <span>RSS URL</span>
            <input
              type="url"
              maxLength={1000}
              value={applicationForm.rssUrl}
              onChange={(event) => updateApplicationForm('rssUrl', event.target.value)}
            />
          </label>
          <label className="public-application-form__wide">
            <span>描述</span>
            <textarea
              maxLength={255}
              rows={3}
              value={applicationForm.description}
              onChange={(event) =>
                updateApplicationForm('description', event.target.value)
              }
            />
          </label>
          <button type="submit" disabled={applicationMutation.isPending}>
            {applicationMutation.isPending ? '提交中' : '提交申请'}
          </button>
        </form>
      </section>
    </div>
  )

  function updateApplicationForm(
    field: keyof typeof emptyApplicationForm,
    value: string,
  ) {
    setApplicationForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmitApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setApplicationNotice(null)
    applicationMutation.mutate({
      name: applicationForm.name.trim(),
      url: applicationForm.url.trim(),
      avatar_url: nullableText(applicationForm.avatarUrl),
      description: nullableText(applicationForm.description),
      rss_url: nullableText(applicationForm.rssUrl),
    })
  }
}

function nullableText(value: string): string | null {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}
