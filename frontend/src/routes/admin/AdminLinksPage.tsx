import { AdminFriendLinksPanel } from '../../features/links/AdminFriendLinksPanel.tsx'

export function AdminLinksPage() {
  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>往来</span>
        <h1>友链管理</h1>
      </section>

      <div className="admin-workspace">
        <AdminFriendLinksPanel />
      </div>
    </div>
  )
}
