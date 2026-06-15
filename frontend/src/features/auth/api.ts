import { apiGet, apiPost } from '../../api/client.ts'

import type { AuthSessionResponse, LoginPayload } from './types.ts'

export function loginAdmin(payload: LoginPayload): Promise<AuthSessionResponse> {
  return apiPost<LoginPayload, AuthSessionResponse>('/admin/auth/login', payload)
}

export function getCurrentAdminSession(): Promise<AuthSessionResponse> {
  return apiGet<AuthSessionResponse>('/admin/auth/me')
}

export function logoutAdmin(csrfToken: string): Promise<{ status: 'ok' }> {
  return apiPost<Record<string, never>, { status: 'ok' }>(
    '/admin/auth/logout',
    {},
    { csrfToken },
  )
}
