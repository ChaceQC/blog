export type PostSummary = {
  id: number
  title: string
  slug: string
  summary: string
  status: 'draft' | 'published'
  category: string
  publishedAt: string
  readingMinutes: number
  coverUrl: string
}

export const samplePosts: PostSummary[] = [
  {
    id: 1,
    title: '建立稳定的发布流程',
    slug: 'quiet-publishing-loop',
    summary: '把草稿、素材、元信息和发布状态放进同一个可维护流程。',
    status: 'published',
    category: '工程实践',
    publishedAt: '2026-06-15',
    readingMinutes: 6,
    coverUrl:
      'https://images.unsplash.com/photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 2,
    title: '先设计文件存储边界',
    slug: 'file-storage-before-uploads',
    summary: '从本地存储开始，同时为后续对象存储适配保留边界。',
    status: 'draft',
    category: '架构设计',
    publishedAt: '草稿',
    readingMinutes: 4,
    coverUrl:
      'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 3,
    title: '把友链当作长期维护的页面',
    slug: 'friend-links-maintained-surface',
    summary: '审核状态、健康检查和分组排序，让链接页面长期保持可用。',
    status: 'published',
    category: '运维记录',
    publishedAt: '2026-06-12',
    readingMinutes: 3,
    coverUrl:
      'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=80',
  },
]
