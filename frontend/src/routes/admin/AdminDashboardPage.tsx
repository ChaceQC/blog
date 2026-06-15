import { useQuery } from '@tanstack/react-query'
import { BarChart3, CheckCircle2, Clock3, ShieldCheck } from 'lucide-react'

import { listAdminPosts } from '../../features/content/api.ts'
import { contentStatusLabels } from '../../features/content/contentLabels.ts'
import { FileQueuePreview } from '../../features/files/FileQueuePreview.tsx'
import { sampleFiles } from '../../features/files/sampleFiles.ts'

export function AdminDashboardPage() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['admin-posts', 'dashboard'],
    queryFn: listAdminPosts,
  })
  const posts = data?.items ?? []
  const publishedCount = posts.filter((post) => post.status === 'published').length
  const draftCount = posts.filter((post) => post.status === 'draft').length
  const metrics = [
    { label: '已发布文章', value: String(publishedCount), icon: CheckCircle2 },
    { label: '草稿', value: String(draftCount), icon: Clock3 },
    { label: '托管文件', value: String(sampleFiles.length), icon: BarChart3 },
    { label: '安全基线', value: '就绪', icon: ShieldCheck },
  ]

  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>DASHBOARD</span>
        <h1>内容状态</h1>
      </section>

      <section className="metric-grid">
        {metrics.map((metric) => {
          const Icon = metric.icon

          return (
            <div className="metric" key={metric.label}>
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          )
        })}
      </section>

      <div className="admin-columns">
        <section className="admin-panel">
          <div className="section-heading">
            <span>最近文章</span>
            <small>{isLoading ? '加载中' : `共 ${posts.length} 篇`}</small>
          </div>
          <div className="admin-table">
            {posts.slice(0, 5).map((post) => (
              <div className="admin-table__row" key={post.id}>
                <span>
                  <strong>{post.title}</strong>
                  <small>/{post.slug}</small>
                </span>
                <small>{contentStatusLabels[post.status]}</small>
              </div>
            ))}
            {isError ? <p className="form-error">文章状态加载失败</p> : null}
            {!isLoading && !isError && posts.length === 0 ? (
              <p className="empty-state">还没有文章。</p>
            ) : null}
          </div>
        </section>
        <FileQueuePreview />
      </div>
    </div>
  )
}
