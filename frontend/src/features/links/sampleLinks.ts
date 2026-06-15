export type FriendLink = {
  id: number
  name: string
  url: string
  description: string
  group: string
  status: 'pending' | 'healthy'
}

export const sampleLinks: FriendLink[] = [
  {
    id: 1,
    name: 'ChaceQC',
    url: 'https://github.com/ChaceQC',
    description: '项目源码、自动化实验和长期维护记录。',
    group: '作者',
    status: 'healthy',
  },
  {
    id: 2,
    name: '静默书房 RSS',
    url: '/feed',
    description: '等待 RSS 接口接入后的公开订阅入口。',
    group: '站点',
    status: 'pending',
  },
]
