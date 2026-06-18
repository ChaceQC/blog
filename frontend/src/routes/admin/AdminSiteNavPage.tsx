import { AdminSiteNavPanel } from '../../features/links/AdminSiteNavPanel.tsx'

export function AdminSiteNavPage() {
  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>导航</span>
        <h1>导航条目</h1>
      </section>

      <div className="admin-workspace">
        <AdminSiteNavPanel />
      </div>
    </div>
  )
}
