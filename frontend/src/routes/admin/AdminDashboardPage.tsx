import { BarChart3, CheckCircle2, Clock3, ShieldCheck } from 'lucide-react'

import { FileQueuePreview } from '../../features/files/FileQueuePreview.tsx'
import { samplePosts } from '../../features/posts/samplePosts.ts'

const metrics = [
  { label: '已发布文章', value: '2', icon: CheckCircle2 },
  { label: '草稿', value: '1', icon: Clock3 },
  { label: '托管文件', value: '2', icon: BarChart3 },
  { label: '安全基线', value: '就绪', icon: ShieldCheck },
]

const postStatusLabels = {
  draft: '草稿',
  published: '已发布',
} satisfies Record<(typeof samplePosts)[number]['status'], string>

export function AdminDashboardPage() {
  return (
    <div className="admin-flow">
      <section className="admin-heading">
        <span>后台工作台</span>
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
            <small>共 {samplePosts.length} 篇</small>
          </div>
          <div className="admin-table">
            {samplePosts.map((post) => (
              <div className="admin-table__row" key={post.id}>
                <span>
                  <strong>{post.title}</strong>
                  <small>{post.category}</small>
                </span>
                <small>{postStatusLabels[post.status]}</small>
              </div>
            ))}
          </div>
        </section>
        <FileQueuePreview />
      </div>
    </div>
  )
}
