import {
  apiGetEncrypted,
  apiPost,
  apiPostEncrypted,
} from '../../api/client.ts'

import type { AuthSessionResponse, LoginPayload } from './types.ts'

export function loginAdmin(payload: LoginPayload): Promise<AuthSessionResponse> {
  return apiPostEncrypted<LoginPayload, AuthSessionResponse>(
    '/admin/auth/login',
    payload,
    'sensitive-v1',
  )
}

export function getCurrentAdminSession(): Promise<AuthSessionResponse> {
  return apiGetEncrypted<AuthSessionResponse>(
    '/admin/auth/me',
    'sensitive-v1',
  )
}

export function refreshAdmin(): Promise<AuthSessionResponse> {
  return apiPostEncrypted<Record<string, never>, AuthSessionResponse>(
    '/admin/auth/refresh',
    {},
    'sensitive-v1',
    { skipAuthRefresh: true },
  )
}

export function logoutAdmin(csrfToken: string): Promise<{ status: 'ok' }> {
  return apiPost<Record<string, never>, { status: 'ok' }>(
    '/admin/auth/logout',
    {},
    { csrfToken, skipAuthRefresh: true },
  )
}
