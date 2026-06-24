import {
  CheckCircle2,
  ExternalLink,
  Link2,
  Save,
  Trash2,
  XCircle,
} from 'lucide-react'

import { ListPager } from '../../components/ListPager.tsx'
import { StatusBadge } from '../../components/StatusBadge.tsx'
import { safePreviewHref } from '../../utils/urls.ts'
import { useAuth } from '../auth/useAuth.ts'
import { AdminFriendLinkGroupsPanel } from './AdminFriendLinkGroupsPanel.tsx'
import {
  formatDateTime,
  formatFriendLinkCheck,
  groupLabel,
  linkStatusLabels,
  parseOptionalId,
} from './friendLinkForm.ts'
import { useAdminFriendLinksEditor } from './useAdminFriendLinksEditor.ts'

import type { ReviewedFriendLinkStatus } from './useAdminFriendLinksEditor.ts'

export function AdminFriendLinksPanel() {
  const { session } = useAuth()
  const editor = useAdminFriendLinksEditor(session)
  const {
    canSaveForm,
    form,
    groups,
    groupsQuery,
    hasUnsavedChanges,
    isCreating,
    isPendingReview,
    isReviewedLink,
    links,
    linksQuery,
    listPageSize,
    notice,
    deleteMutation,
    reviewAndSaveMutation,
    safeListPage,
    saveMutation,
    selectLink,
    selectedLink,
    setListPage,
    startCreating,
    updateForm,
    visibleLinks,
  } = editor

  return (
    <>
      <div className="admin-list-column">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>友链审核</span>
            <small>{linksQuery.isLoading ? '加载中' : `共 ${links.length} 条`}</small>
            <button
              className="text-button text-button--muted"
              onClick={startCreating}
              type="button"
            >
              <Link2 size={14} strokeWidth={1.8} aria-hidden="true" />
              新建友链
            </button>
          </div>
          {linksQuery.isError ? <p className="form-error">友链列表加载失败</p> : null}
          <div className="content-list">
            {visibleLinks.map((link) => (
              <button
                className={
                  link.id === selectedLink?.id ? 'content-row active' : 'content-row'
                }
                key={link.id}
                onClick={() => selectLink(link)}
                type="button"
              >
                <span>
                  <strong>{link.name}</strong>
                  <small>{link.url}</small>
                  <small>{formatFriendLinkCheck(link)}</small>
                </span>
                <StatusBadge tone={link.status}>{linkStatusLabels[link.status]}</StatusBadge>
              </button>
            ))}
          </div>
          <ListPager
            page={safeListPage}
            pageSize={listPageSize}
            totalItems={links.length}
            isLoading={linksQuery.isLoading}
            variant="admin"
            onPageChange={setListPage}
          />
          {!linksQuery.isLoading && links.length === 0 ? (
            <p className="empty-state">还没有待管理的友链。</p>
          ) : null}
        </section>

        <section className="admin-panel admin-panel--groups">
          <AdminFriendLinkGroupsPanel
            groups={groups}
            isLoading={groupsQuery.isLoading}
          />
        </section>
      </div>

      <section className="admin-panel admin-panel--editor">
        <div className="section-heading">
          <span>{isCreating ? '新建友链' : '友链编辑'}</span>
          <small>{notice ?? groupLabel(form.groupId, groups) ?? '未分组'}</small>
        </div>
        {selectedLink || isCreating ? (
          <div className="admin-detail">
            <div className="admin-title-row">
              <span>
                <strong>{form.name || '未命名友链'}</strong>
                <small>{form.description || '暂无描述'}</small>
              </span>
              <a
                className="icon-button"
                href={safePreviewHref(form.url)}
                aria-label="打开友链"
              >
                <ExternalLink size={17} strokeWidth={1.8} aria-hidden="true" />
              </a>
            </div>
            <form className="content-form">
              <div className="form-grid form-grid--two">
                <label>
                  名称
                  <input
                    onChange={(event) => updateForm('name', event.target.value)}
                    value={form.name}
                  />
                </label>
                {isReviewedLink ? (
                  <label>
                    状态
                    <select
                      onChange={(event) =>
                        updateForm(
                          'status',
                          event.target.value as ReviewedFriendLinkStatus,
                        )
                      }
                      value={form.status}
                    >
                      <option value="healthy">通过</option>
                      <option value="rejected">已拒绝</option>
                    </select>
                  </label>
                ) : null}
                <label>
                  分组
                  <select
                    onChange={(event) =>
                      updateForm('groupId', parseOptionalId(event.target.value))
                    }
                    value={form.groupId ?? ''}
                  >
                    <option value="">未分组</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                站点 URL
                <input
                  onChange={(event) => updateForm('url', event.target.value)}
                  value={form.url}
                />
              </label>
              <label>
                描述
                <textarea
                  onChange={(event) => updateForm('description', event.target.value)}
                  rows={3}
                  value={form.description}
                />
              </label>
              <div className="form-grid form-grid--two">
                <label>
                  头像 URL
                  <input
                    onChange={(event) => updateForm('avatarUrl', event.target.value)}
                    value={form.avatarUrl}
                  />
                </label>
                <label>
                  RSS URL
                  <input
                    onChange={(event) => updateForm('rssUrl', event.target.value)}
                    value={form.rssUrl}
                  />
                </label>
              </div>
              <label>
                排序
                <input
                  min={0}
                  onChange={(event) =>
                    updateForm('sortOrder', Number(event.target.value))
                  }
                  type="number"
                  value={form.sortOrder}
                />
              </label>
            </form>
            {selectedLink ? (
              <dl className="detail-list">
                <div>
                  <dt>状态检查</dt>
                  <dd>{formatFriendLinkCheck(selectedLink)}</dd>
                </div>
                <div>
                  <dt>最近检查</dt>
                  <dd>{formatDateTime(selectedLink.last_checked_at)}</dd>
                </div>
              </dl>
            ) : null}
            <div className="form-actions">
              {isPendingReview ? (
                <>
                  <button
                    className="text-button"
                    disabled={!canSaveForm || reviewAndSaveMutation.isPending}
                    onClick={() => reviewAndSaveMutation.mutate('healthy')}
                    type="button"
                  >
                    <CheckCircle2 size={17} strokeWidth={1.8} aria-hidden="true" />
                    {reviewAndSaveMutation.isPending ? '保存中' : '通过'}
                  </button>
                  <button
                    className="text-button text-button--muted"
                    disabled={!canSaveForm || reviewAndSaveMutation.isPending}
                    onClick={() => reviewAndSaveMutation.mutate('rejected')}
                    type="button"
                  >
                    <XCircle size={17} strokeWidth={1.8} aria-hidden="true" />
                    拒绝
                  </button>
                </>
              ) : (
                <button
                  className="text-button"
                  disabled={
                    !canSaveForm || !hasUnsavedChanges || saveMutation.isPending
                  }
                  onClick={() => saveMutation.mutate()}
                  type="button"
                >
                  <Save size={17} strokeWidth={1.8} aria-hidden="true" />
                  {saveMutation.isPending ? '保存中' : '保存'}
                </button>
              )}
              <button
                className="text-button text-button--danger"
                disabled={!selectedLink || isCreating || deleteMutation.isPending}
                onClick={() => {
                  if (window.confirm('确定删除这条友链吗？')) {
                    deleteMutation.mutate()
                  }
                }}
                type="button"
              >
                <Trash2 size={17} strokeWidth={1.8} aria-hidden="true" />
                {deleteMutation.isPending ? '删除中' : '删除'}
              </button>
            </div>
          </div>
        ) : (
          <p className="empty-state">没有选中的友链。</p>
        )}
      </section>
    </>
  )

}
