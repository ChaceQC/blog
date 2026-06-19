import { describe, expect, it } from 'vitest'

import { safePageIndex } from './usePagedItems.ts'

describe('safePageIndex', () => {
  it('clamps invalid and out-of-range pages', () => {
    expect(safePageIndex(Number.NaN, 40, 10)).toBe(0)
    expect(safePageIndex(-2, 40, 10)).toBe(0)
    expect(safePageIndex(99, 35, 10)).toBe(3)
  })

  it('keeps empty lists on the first page', () => {
    expect(safePageIndex(3, 0, 10)).toBe(0)
  })
})
