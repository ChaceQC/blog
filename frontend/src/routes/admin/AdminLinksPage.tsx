import { CheckCircle2, ExternalLink, Link2, Navigation, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'

import { StatusBadge } from '../../components/StatusBadge.tsx'
import { sampleLinks } from '../../features/links/sampleLinks.ts'
import { sampleSites } from '../../features/sites/sampleSites.ts'

import type { FriendLink } from '../../features/links/sampleLinks.ts'

const linkStatusLabels = {
  healthy: '通过',
  pending: '待审核',
} satisfies Record<FriendLink['status'], string>

export function AdminLinksPage() {
  const [selectedLinkId, setSelectedLinkId] = useState(sampleLinks[0]?.id ?? 0)
  const selectedLink = useMemo(
    () => sampleLinks.find((link) => link.id === selectedLinkId) ?? null,
    [selectedLinkId],
  )

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
            <small>共 {sampleLinks.length} 条</small>
          </div>
          <div className="content-list">
            {sampleLinks.map((link) => (
              <button
                className={
                  link.id === selectedLinkId ? 'content-row active' : 'content-row'
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
        </section>

        <section className="admin-panel admin-panel--editor">
          <div className="section-heading">
            <span>审核详情</span>
            <small>{selectedLink?.group ?? '未分组'}</small>
          </div>
          {selectedLink ? (
            <div className="admin-detail">
              <div className="admin-title-row">
                <span>
                  <strong>{selectedLink.name}</strong>
                  <small>{selectedLink.description}</small>
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
                  <dd>{selectedLink.group}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{linkStatusLabels[selectedLink.status]}</dd>
                </div>
              </dl>
              <div className="form-actions">
                <button className="text-button" disabled type="button">
                  <CheckCircle2 size={17} strokeWidth={1.8} aria-hidden="true" />
                  通过
                </button>
                <button className="text-button text-button--muted" disabled type="button">
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
              {sampleSites.length} 个
            </small>
          </div>
          <div className="admin-stack-list">
            {sampleSites.map((site) => (
              <a href={site.url} key={site.id}>
                <span>
                  <strong>{site.title}</strong>
                  <small>{site.description}</small>
                </span>
                <small>{site.group}</small>
              </a>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
