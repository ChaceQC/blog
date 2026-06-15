export type ManagedFile = {
  id: number
  displayName: string
  objectKey: string
  mimeType: string
  size: string
  visibility: 'public' | 'private'
  usage: string
  updatedAt: string
}

export const sampleFiles: ManagedFile[] = [
  {
    id: 1,
    displayName: '封面书桌.jpg',
    objectKey: 'uploads/public/2026/06/cover-desk.jpg',
    mimeType: 'image/jpeg',
    size: '420 KB',
    visibility: 'public',
    usage: '文章封面',
    updatedAt: '2026-06-15',
  },
  {
    id: 2,
    displayName: '发布记录.pdf',
    objectKey: 'uploads/private/2026/06/launch-notes.pdf',
    mimeType: 'application/pdf',
    size: '1.2 MB',
    visibility: 'private',
    usage: '私有附件',
    updatedAt: '2026-06-15',
  },
]
