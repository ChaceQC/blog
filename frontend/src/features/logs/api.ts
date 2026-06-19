import { apiGetEncrypted } from '../../api/client.ts'

import type {
  AccessLogListResponse,
  AuditLogListResponse,
  LoginLogListResponse,
  SecurityEventListResponse,
} from './types.ts'

type LogListParams = {
  limit: number
  offset: number
}

export function listAuditLogs(params: LogListParams): Promise<AuditLogListResponse> {
  return apiGetEncrypted<AuditLogListResponse>(
    `/admin/audit-logs?${logQuery(params)}`,
    'sensitive-v1',
  )
}

export function listAccessLogs(
  params: LogListParams,
): Promise<AccessLogListResponse> {
  return apiGetEncrypted<AccessLogListResponse>(
    `/admin/access-logs?${logQuery(params)}`,
    'sensitive-v1',
  )
}

export function listLoginLogs(params: LogListParams): Promise<LoginLogListResponse> {
  return apiGetEncrypted<LoginLogListResponse>(
    `/admin/login-logs?${logQuery(params)}`,
    'sensitive-v1',
  )
}

export function listSecurityEvents(
  params: LogListParams,
): Promise<SecurityEventListResponse> {
  return apiGetEncrypted<SecurityEventListResponse>(
    `/admin/security-events?${logQuery(params)}`,
    'sensitive-v1',
  )
}

function logQuery({ limit, offset }: LogListParams): string {
  return new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  }).toString()
}
