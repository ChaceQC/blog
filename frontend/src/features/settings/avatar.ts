export const DEFAULT_AVATAR_URL = '/default-avatar.svg'

export function fallbackToDefaultAvatar(event: {
  currentTarget: HTMLImageElement
}) {
  if (event.currentTarget.src.endsWith(DEFAULT_AVATAR_URL)) {
    return
  }
  event.currentTarget.src = DEFAULT_AVATAR_URL
}
