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
    name: '设计札记',
    url: 'https://example.com',
    description: '界面写作、系统思考和克制的软件实践。',
    group: '朋友',
    status: 'healthy',
  },
  {
    id: 2,
    name: '实验日志',
    url: 'https://example.org',
    description: '围绕工具、部署和自动化的小型实验记录。',
    group: '项目',
    status: 'pending',
  },
]
