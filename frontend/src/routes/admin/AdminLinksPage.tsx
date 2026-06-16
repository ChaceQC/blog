import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ExternalLink, Link2, Navigation, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'

import { StatusBadge } from '../../components/StatusBadge.tsx'
import {
  listAdminFriendLinks,
  listAdminSiteNavItems,
  reviewAdminFriendLink,
} from '../../features/links/api.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

import type { AdminFriendLinkStatus } from '../../features/links/types.ts'

const linkStatusLabels = {
  healthy: '通过',
  pending: '待审核',
  rejected: '已拒绝',
} satisfies Record<AdminFriendLinkStatus, string>

export function AdminLinksPage() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const linksQuery = useQuery({
    queryKey: ['admin-friend-links'],
    queryFn: listAdminFriendLinks,
  })
  const sitesQuery = useQuery({
    queryKey: ['admin-site-nav-items'],
    queryFn: listAdminSiteNavItems,
  })
  const links = useMemo(() => linksQuery.data?.items ?? [], [linksQuery.data])
  const sites = useMemo(() => sitesQuery.data?.items ?? [], [sitesQuery.data])
  const selectedLink = useMemo(
    () =>
      links.find((link) => link.id === selectedLinkId) ?? links[0] ?? null,
    [links, selectedLinkId],
  )
  const reviewMutation = useMutation({
    mutationFn: async (status: AdminFriendLinkStatus) => {
      if (!session || !selectedLink) {
        throw new Error('当前会话已失效')
      }
      return reviewAdminFriendLink(selectedLink.id, { status }, session.csrfToken)
    },
    onSuccess: (link) => {
      setSelectedLinkId(link.id)
      queryClient.invalidateQueries({ queryKey: ['admin-friend-links'] })
      setNotice('审核状态已更新')
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : '审核更新失败')
    },
  })

  return (
    <div className="admin-flow">
      <section className="admin-heading admin-heading--with-action">
        <span>LINKS</span>
        <h1>友链与导航</h1>
        <button className="text-button admin-heading__action" disabled type="button">
          <Link2 size={17} strokeWidth={1.8} aria-hidden="true" />
          新建条目
        </button>
      </section>

      <div className="admin-workspace">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>友链审核</span>
            <small>{linksQuery.isLoading ? '加载中' : `共 ${links.length} 条`}</small>
          </div>
          {linksQuery.isError ? <p className="form-error">友链列表加载失败</p> : null}
          <div className="content-list">
            {links.map((link) => (
              <button
                className={
                  link.id === selectedLink?.id ? 'content-row active' : 'content-row'
                }
                key={link.id}
                onClick={() => setSelectedLinkId(link.id)}
                type="button"
              >
                <span>
                  <strong>{link.name}</strong>
                  <small>{link.url}</small>
                </span>
                <StatusBadge tone={link.status}>{linkStatusLabels[link.status]}</StatusBadge>
              </button>
            ))}
          </div>
          {!linksQuery.isLoading && links.length === 0 ? (
            <p className="empty-state">还没有待管理的友链。</p>
          ) : null}
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>审核详情</span>
            <small>{notice ?? selectedLink?.group_name ?? '未分组'}</small>
          </div>
          {selectedLink ? (
            <div className="admin-detail">
              <div className="admin-title-row">
                <span>
                  <strong>{selectedLink.name}</strong>
                  <small>{selectedLink.description ?? '暂无描述'}</small>
                </span>
                <a className="icon-button" href={selectedLink.url} aria-label="打开友链">
                  <ExternalLink size={17} strokeWidth={1.8} aria-hidden="true" />
                </a>
              </div>
              <dl className="detail-list">
                <div>
                  <dt>站点 URL</dt>
                  <dd>{selectedLink.url}</dd>
                </div>
                <div>
                  <dt>分组</dt>
                  <dd>{selectedLink.group_name ?? '未分组'}</dd>
                </div>
                <div>
                  <dt>RSS</dt>
                  <dd>{selectedLink.rss_url ?? '未填写'}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{linkStatusLabels[selectedLink.status]}</dd>
                </div>
              </dl>
              <div className="form-actions">
                <button
                  className="text-button"
                  disabled={!session || reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate('healthy')}
                  type="button"
                >
                  <CheckCircle2 size={17} strokeWidth={1.8} aria-hidden="true" />
                  通过
                </button>
                <button
                  className="text-button text-button--muted"
                  disabled={!session || reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate('rejected')}
                  type="button"
                >
                  <XCircle size={17} strokeWidth={1.8} aria-hidden="true" />
                  拒绝
                </button>
              </div>
            </div>
          ) : (
            <p className="empty-state">没有选中的友链。</p>
          )}
        </section>

        <section className="admin-panel admin-panel--preview">
          <div className="section-heading">
            <span>导航条目</span>
            <small>
              <Navigation size={14} strokeWidth={1.8} aria-hidden="true" />
              {sitesQuery.isLoading ? '加载中' : `${sites.length} 个`}
            </small>
          </div>
          {sitesQuery.isError ? <p className="form-error">导航条目加载失败</p> : null}
          <div className="admin-stack-list">
            {sites.map((site) => (
              <a href={site.url} key={site.id}>
                <span>
                  <strong>{site.title}</strong>
                  <small>{site.description ?? '暂无描述'}</small>
                </span>
                <small>{site.group_name ?? '未分组'}</small>
              </a>
            ))}
          </div>
          {!sitesQuery.isLoading && sites.length === 0 ? (
            <p className="empty-state">还没有导航条目。</p>
          ) : null}
        </section>
      </div>
    </div>
  )
}
