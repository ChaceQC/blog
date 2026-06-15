export const adminAccess = {
  dashboard: [],
  files: ['file:upload', 'file:delete'],
  links: ['friend_link:review', 'site_nav:write'],
  settings: ['setting:write'],
} as const
