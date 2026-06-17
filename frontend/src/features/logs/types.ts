export type AuditLogItem = {
  id: number
  actor_id: number | null
  action: string
  entity_type: string
  entity_id: number | null
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  ip: string | null
  user_agent: string | null
  created_at: string
}

export type AccessLogItem = {
  id: number
  access_type: string
  method: string
  path: string
  status_code: number
  entity_type: string | null
  entity_id: number | null
  ip: string | null
  user_agent: string | null
  detail_json: Record<string, unknown> | null
  created_at: string
}

export type LoginLogItem = {
  id: number
  user_id: number | null
  username: string
  success: boolean
  ip: string | null
  user_agent: string | null
  reason: string | null
  created_at: string
}

export type SecurityEventItem = {
  id: number
  event_type: string
  severity: string
  actor_id: number | null
  ip: string | null
  user_agent: string | null
  path: string | null
  detail_json: Record<string, unknown> | null
  created_at: string
}

export type AccessLogListResponse = {
  items: AccessLogItem[]
}

export type AuditLogListResponse = {
  items: AuditLogItem[]
}

export type LoginLogListResponse = {
  items: LoginLogItem[]
}

export type SecurityEventListResponse = {
  items: SecurityEventItem[]
}
