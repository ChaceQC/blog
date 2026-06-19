import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listAccessLogs,
  listAuditLogs,
  listLoginLogs,
  listSecurityEvents,
} from './api.ts'

const mocks = vi.hoisted(() => ({
  apiGetEncrypted: vi.fn(),
}))

vi.mock('../../api/client.ts', () => ({
  apiGetEncrypted: mocks.apiGetEncrypted,
}))

describe('logs api', () => {
  beforeEach(() => {
    mocks.apiGetEncrypted.mockResolvedValue({ items: [] })
    mocks.apiGetEncrypted.mockClear()
  })

  it('passes limit and offset to audit logs endpoint', async () => {
    await listAuditLogs({ limit: 11, offset: 20 })

    expect(mocks.apiGetEncrypted).toHaveBeenCalledWith(
      '/admin/audit-logs?limit=11&offset=20',
      'sensitive-v1',
    )
  })

  it('uses backend pagination for every log kind', async () => {
    await listAccessLogs({ limit: 11, offset: 10 })
    await listLoginLogs({ limit: 11, offset: 10 })
    await listSecurityEvents({ limit: 11, offset: 10 })

    expect(mocks.apiGetEncrypted).toHaveBeenNthCalledWith(
      1,
      '/admin/access-logs?limit=11&offset=10',
      'sensitive-v1',
    )
    expect(mocks.apiGetEncrypted).toHaveBeenNthCalledWith(
      2,
      '/admin/login-logs?limit=11&offset=10',
      'sensitive-v1',
    )
    expect(mocks.apiGetEncrypted).toHaveBeenNthCalledWith(
      3,
      '/admin/security-events?limit=11&offset=10',
      'sensitive-v1',
    )
  })
})
