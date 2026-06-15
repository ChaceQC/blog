import { apiGet, apiPost } from '../../api/client.ts'

import type { AuthUser, LoginPayload, TokenPair } from './types.ts'

export function loginAdmin(payload: LoginPayload): Promise<TokenPair> {
  return apiPost<LoginPayload, TokenPair>('/admin/auth/login', payload)
}

export function getCurrentAdminUser(accessToken: string): Promise<AuthUser> {
  return apiGet<AuthUser>('/admin/auth/me', { accessToken })
}

export function logoutAdmin(refreshToken: string): Promise<{ status: 'ok' }> {
  return apiPost<{ refresh_token: string }, { status: 'ok' }>(
    '/admin/auth/logout',
    { refresh_token: refreshToken },
  )
}
