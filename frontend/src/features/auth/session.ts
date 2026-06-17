import type { AuthSessionResponse, AuthUser } from './types.ts'

export type AuthSession = {
  csrfToken: string
  expiresAt: number
  expiresIn: number
  user: AuthUser
}

export function createAuthSession(response: AuthSessionResponse): AuthSession {
  return {
    csrfToken: response.csrf_token,
    expiresAt: Date.now() + response.expires_in * 1000,
    expiresIn: response.expires_in,
    user: response.user,
  }
}
