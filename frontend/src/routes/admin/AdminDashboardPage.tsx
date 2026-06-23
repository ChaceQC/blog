import { useQuery } from '@tanstack/react-query'
import { BarChart3, CheckCircle2, Clock3, Sparkles } from 'lucide-react'

import { listAdminPosts } from '../../features/content/api.ts'
import { contentStatusLabels } from '../../features/content/contentLabels.ts'
import { listAdminFiles } from '../../features/files/adminApi.ts'
import { FileQueuePreview } from '../../features/files/FileQueuePreview.tsx'

export function AdminDashboardPage() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['admin-posts', 'dashboard'],
    queryFn: listAdminPosts,
  })
  const filesQuery = useQuery({
    queryKey: ['admin-files'],
    queryFn: listAdminFiles,
  })
  const posts = data?.items ?? []
  const files = filesQuery.data?.items ?? []
  const publishedCount = posts.filter((post) => post.status === 'published').length
  const draftCount = posts.filter((post) => post.status === 'draft').length
  const metrics = [
    { label: '已发布文章', value: String(publishedCount), icon: CheckCircle2 },
    { label: '草稿', value: String(draftCount), icon: Clock3 },
    {
      label: '素材',
      value: filesQuery.isLoading ? '...' : String(files.length),
      icon: BarChart3,
    },
    { label: '今日状态', value: '安静', icon: Sparkles },
  ]

  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>书房</span>
        <h1>今天写点什么</h1>
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
            {isError ? <p className="form-error">文章列表暂时打不开</p> : null}
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
