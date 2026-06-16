export const adminAccess = {
  dashboard: [],
  posts: ['post:read', 'post:write', 'post:publish'],
  pages: ['page:write'],
  files: ['file:upload', 'file:delete'],
  links: ['friend_link:review', 'site_nav:write'],
  logs: ['audit_log:read'],
  settings: ['setting:write'],
} as const
