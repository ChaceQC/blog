import { apiGetEncrypted } from '../../api/client.ts'

import type {
  AccessLogListResponse,
  AuditLogListResponse,
  LoginLogListResponse,
  SecurityEventListResponse,
} from './types.ts'

export function listAuditLogs(): Promise<AuditLogListResponse> {
  return apiGetEncrypted<AuditLogListResponse>(
    '/admin/audit-logs?limit=50',
    'sensitive-v1',
  )
}

export function listAccessLogs(): Promise<AccessLogListResponse> {
  return apiGetEncrypted<AccessLogListResponse>(
    '/admin/access-logs?limit=50',
    'sensitive-v1',
  )
}

export function listLoginLogs(): Promise<LoginLogListResponse> {
  return apiGetEncrypted<LoginLogListResponse>(
    '/admin/login-logs?limit=50',
    'sensitive-v1',
  )
}

export function listSecurityEvents(): Promise<SecurityEventListResponse> {
  return apiGetEncrypted<SecurityEventListResponse>(
    '/admin/security-events?limit=50',
    'sensitive-v1',
  )
}
