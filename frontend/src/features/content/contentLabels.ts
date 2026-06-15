import type { ContentStatus, PostVisibility } from './types.ts'

export const contentStatusLabels = {
  draft: '草稿',
  published: '已发布',
  scheduled: '定时',
  archived: '归档',
} satisfies Record<ContentStatus, string>

export const postVisibilityLabels = {
  public: '公开',
  hidden: '隐藏',
  private: '私有',
} satisfies Record<PostVisibility, string>
