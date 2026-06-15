import type { AuthSessionResponse, AuthUser } from './types.ts'

export type AuthSession = {
  csrfToken: string
  expiresIn: number
  user: AuthUser
}

export function createAuthSession(response: AuthSessionResponse): AuthSession {
  return {
    csrfToken: response.csrf_token,
    expiresIn: response.expires_in,
    user: response.user,
  }
}
