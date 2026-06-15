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
    title: '状态页',
    url: 'https://status.example.com',
    description: '服务健康状态和可用性检查。',
    group: '自托管',
  },
  {
    id: 2,
    title: '文档站',
    url: 'https://docs.example.com',
    description: '部署记录、恢复流程和运维手册。',
    group: '自托管',
  },
  {
    id: 3,
    title: '写作队列',
    url: 'https://notes.example.com',
    description: '等待整理和发布的文章想法。',
    group: '工作流',
  },
]
