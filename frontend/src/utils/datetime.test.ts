import { describe, expect, it } from 'vitest'

import { formatChinaShortDateTime, parseApiTime } from './datetime.ts'

describe('datetime utilities', () => {
  it('treats API timestamps without an explicit zone as UTC', () => {
    expect(parseApiTime('2026-06-29T03:53:00')).toBe(
      Date.parse('2026-06-29T03:53:00Z'),
    )
  })

  it('formats API timestamps in Beijing time', () => {
    expect(formatChinaShortDateTime('2026-06-29T03:53:00', 'invalid')).toBe(
      '06/29 11:53',
    )
  })

  it('does not reinterpret timestamps that already include a timezone', () => {
    expect(
      formatChinaShortDateTime('2026-06-29T03:53:00+08:00', 'invalid'),
    ).toBe('06/29 03:53')
  })
})
