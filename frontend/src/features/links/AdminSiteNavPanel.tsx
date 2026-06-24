import { ExternalLink, Navigation, Save, Trash2 } from 'lucide-react'

import { ListPager } from '../../components/ListPager.tsx'
import { parseOptionalId } from '../../utils/formText.ts'
import { safePreviewHref } from '../../utils/urls.ts'
import { AdminSiteNavGroupsPanel } from './AdminSiteNavGroupsPanel.tsx'
import { useAdminSiteNavEditor } from './useAdminSiteNavEditor.ts'
import { useAuth } from '../auth/useAuth.ts'

import type {
  AdminSiteNavGroup,
  AdminSiteNavOpenTarget,
  AdminSiteNavVisibility,
} from './types.ts'

export function AdminSiteNavPanel() {
  const { session } = useAuth()
  const editor = useAdminSiteNavEditor(session)
  const {
    groups,
    groupsQuery,
    isCreatingSite,
    listPageSize,
    safeListPage,
    deleteSiteMutation,
    saveSiteMutation,
    selectSite,
    selectedSite,
    setListPage,
    siteForm,
    siteNotice,
    sites,
    sitesQuery,
    startCreatingSite,
    updateSiteForm,
    visibleSites,
  } = editor

  return (
    <>
      <div className="admin-list-column">
        <section className="admin-panel admin-panel--list">
          <div className="section-heading">
            <span>导航条目</span>
            <small>{sitesQuery.isLoading ? '加载中' : `共 ${sites.length} 条`}</small>
            <button
              className="text-button text-button--muted"
              onClick={startCreatingSite}
              type="button"
            >
              <Navigation size={14} strokeWidth={1.8} aria-hidden="true" />
              新建导航
            </button>
          </div>
          {sitesQuery.isError ? <p className="form-error">导航条目加载失败</p> : null}
          <div className="content-list">
            {visibleSites.map((site) => (
              <button
                className={
                  site.id === selectedSite?.id ? 'content-row active' : 'content-row'
                }
                key={site.id}
                onClick={() => selectSite(site)}
                type="button"
              >
                <span>
                  <strong>{site.title}</strong>
                  <small>{site.description ?? site.url}</small>
                  <small>{site.group_name ?? '未分组'}</small>
                </span>
                <small>{site.open_target === 'blank' ? '新标签' : '当前页'}</small>
              </button>
            ))}
          </div>
          <ListPager
            page={safeListPage}
            pageSize={listPageSize}
            totalItems={sites.length}
            isLoading={sitesQuery.isLoading}
            variant="admin"
            onPageChange={setListPage}
          />
          {!sitesQuery.isLoading && sites.length === 0 ? (
            <p className="empty-state">还没有导航条目。</p>
          ) : null}
        </section>

        <section className="admin-panel admin-panel--groups">
          <AdminSiteNavGroupsPanel
            groups={groups}
            isLoading={groupsQuery.isLoading}
          />
        </section>
      </div>

      <section className="admin-panel admin-panel--editor">
        <div className="section-heading">
          <span>{isCreatingSite ? '新建导航' : '导航编辑'}</span>
          <small>{siteNotice ?? groupLabel(siteForm.groupId, groups) ?? '未分组'}</small>
        </div>
        {selectedSite || isCreatingSite ? (
          <div className="admin-detail">
            <div className="admin-title-row">
              <span>
                <strong>{siteForm.title || '未命名导航'}</strong>
                <small>{siteForm.description || siteForm.url || '暂无描述'}</small>
              </span>
              <a
                className="icon-button"
                href={safePreviewHref(siteForm.url)}
                aria-label="打开导航链接"
              >
                <ExternalLink size={17} strokeWidth={1.8} aria-hidden="true" />
              </a>
            </div>
            <form className="content-form">
              <label>
                标题
                <input
                  onChange={(event) => updateSiteForm('title', event.target.value)}
                  value={siteForm.title}
                />
              </label>
              <label>
                URL
                <input
                  onChange={(event) => updateSiteForm('url', event.target.value)}
                  value={siteForm.url}
                />
              </label>
              <label>
                描述
                <textarea
                  onChange={(event) =>
                    updateSiteForm('description', event.target.value)
                  }
                  rows={2}
                  value={siteForm.description}
                />
              </label>
              <div className="form-grid form-grid--two">
                <label>
                  分组
                  <select
                    onChange={(event) =>
                      updateSiteForm('groupId', parseOptionalId(event.target.value))
                    }
                    value={siteForm.groupId ?? ''}
                  >
                    <option value="">未分组</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  打开方式
                  <select
                    onChange={(event) =>
                      updateSiteForm(
                        'openTarget',
                        event.target.value as AdminSiteNavOpenTarget,
                      )
                    }
                    value={siteForm.openTarget}
                  >
                    <option value="blank">新标签打开</option>
                    <option value="self">当前页打开</option>
                  </select>
                </label>
              </div>
              <div className="form-grid form-grid--two">
                <label>
                  可见性
                  <select
                    onChange={(event) =>
                      updateSiteForm(
                        'visibility',
                        event.target.value as AdminSiteNavVisibility,
                      )
                    }
                    value={siteForm.visibility}
                  >
                    <option value="public">公开</option>
                    <option value="hidden">隐藏</option>
                    <option value="private">后台可见</option>
                  </select>
                </label>
                <label>
                  标签
                  <input
                    onChange={(event) =>
                      updateSiteForm('tagsText', event.target.value)
                    }
                    value={siteForm.tagsText}
                  />
                </label>
              </div>
              <div className="form-grid form-grid--two">
                <label>
                  图标 URL
                  <input
                    onChange={(event) => updateSiteForm('iconUrl', event.target.value)}
                    value={siteForm.iconUrl}
                  />
                </label>
                <label>
                  排序
                  <input
                    min={0}
                    onChange={(event) =>
                      updateSiteForm('sortOrder', Number(event.target.value))
                    }
                    type="number"
                    value={siteForm.sortOrder}
                  />
                </label>
              </div>
              <div className="form-actions">
                <button
                  className="text-button"
                  disabled={
                    !session ||
                    saveSiteMutation.isPending ||
                    siteForm.title.trim() === '' ||
                    siteForm.url.trim() === ''
                  }
                  onClick={() => saveSiteMutation.mutate()}
                  type="button"
                >
                  <Save size={17} strokeWidth={1.8} aria-hidden="true" />
                  {saveSiteMutation.isPending ? '保存中' : '保存导航'}
                </button>
                <button
                  className="text-button text-button--danger"
                  disabled={
                    !selectedSite ||
                    isCreatingSite ||
                    deleteSiteMutation.isPending
                  }
                  onClick={() => {
                    if (window.confirm('确定删除这个导航吗？')) {
                      deleteSiteMutation.mutate()
                    }
                  }}
                  type="button"
                >
                  <Trash2 size={17} strokeWidth={1.8} aria-hidden="true" />
                  {deleteSiteMutation.isPending ? '删除中' : '删除'}
                </button>
              </div>
            </form>
          </div>
        ) : (
          <p className="empty-state">没有选中的导航。</p>
        )}
      </section>
    </>
  )

}

function groupLabel(
  groupId: number | null,
  groups: AdminSiteNavGroup[],
): string | null {
  if (groupId === null) {
    return null
  }
  return groups.find((group) => group.id === groupId)?.name ?? null
}
