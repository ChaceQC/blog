import { apiPost } from '../../api/client.ts'

import type { LoginPayload, TokenPair } from './types.ts'

export function loginAdmin(payload: LoginPayload): Promise<TokenPair> {
  return apiPost<LoginPayload, TokenPair>('/admin/auth/login', payload)
}

export function logoutAdmin(refreshToken: string): Promise<{ status: 'ok' }> {
  return apiPost<{ refresh_token: string }, { status: 'ok' }>(
    '/admin/auth/logout',
    { refresh_token: refreshToken },
  )
}
