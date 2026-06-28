export const adminAccess = {
  dashboard: [],
  posts: ['post:read', 'post:write', 'post:publish'],
  comments: ['comment:review'],
  pages: ['page:write'],
  files: ['file:upload', 'file:delete'],
  links: ['friend_link:review'],
  siteNav: ['site_nav:write'],
  logs: ['audit_log:read'],
  settings: ['setting:write'],
} as const
