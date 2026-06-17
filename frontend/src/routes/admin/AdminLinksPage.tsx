import { AdminFriendLinksPanel } from '../../features/links/AdminFriendLinksPanel.tsx'
import { AdminSiteNavPanel } from '../../features/links/AdminSiteNavPanel.tsx'

export function AdminLinksPage() {
  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>往来</span>
        <h1>友链与导航</h1>
      </section>

      <div className="admin-workspace">
        <AdminFriendLinksPanel />
        <AdminSiteNavPanel />
      </div>
    </div>
  )
}
