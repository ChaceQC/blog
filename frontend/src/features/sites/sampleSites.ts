export type SiteItem = {
  id: number
  title: string
  url: string
  description: string
  group: string
}

export const sampleSites: SiteItem[] = [
  {
    id: 1,
    title: '后端健康检查',
    url: 'http://127.0.0.1:18080/healthz',
    description: '本地开发时检查 API 进程是否可用。',
    group: '自托管',
  },
  {
    id: 2,
    title: 'GitHub 仓库',
    url: 'https://github.com/ChaceQC/blog',
    description: '源码、提交记录和后续发布入口。',
    group: '项目',
  },
  {
    id: 3,
    title: '后台文章',
    url: '/admin/posts',
    description: '进入文章草稿、发布和预览工作台。',
    group: '工作流',
  },
]
