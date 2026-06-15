import type { AuthUser, TokenPair } from './types.ts'

const STORAGE_KEY = 'blog.admin.session'

export type AuthSession = {
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: AuthUser
}

export function createAuthSession(tokens: TokenPair): AuthSession {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresIn: tokens.expires_in,
    user: tokens.user,
  }
}

export function readAuthSession(): AuthSession | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    const parsed: unknown = JSON.parse(raw)
    if (isAuthSession(parsed)) {
      return parsed
    }
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
  }

  return null
}

export function saveAuthSession(session: AuthSession): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearAuthSession(): void {
  window.localStorage.removeItem(STORAGE_KEY)
}

function isAuthSession(value: unknown): value is AuthSession {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const session = value as Partial<AuthSession>
  return (
    typeof session.accessToken === 'string' &&
    typeof session.refreshToken === 'string' &&
    typeof session.expiresIn === 'number' &&
    typeof session.user === 'object' &&
    session.user !== null
  )
}
