import { describe, expect, it } from 'vitest'

import { safePreviewHref } from './urls.ts'

describe('safePreviewHref', () => {
  it('allows public protocols and public site paths', () => {
    expect(safePreviewHref('https://example.test/path')).toBe(
      'https://example.test/path',
    )
    expect(safePreviewHref('mailto:admin@example.test')).toBe(
      'mailto:admin@example.test',
    )
    expect(safePreviewHref('/posts')).toBe('/posts')
  })

  it('rejects dangerous protocols and sensitive site paths', () => {
    expect(safePreviewHref('javascript:alert(1)')).toBe('#')
    expect(safePreviewHref('//example.test/path')).toBe('#')
    expect(safePreviewHref('/admin')).toBe('#')
    expect(safePreviewHref('/api/admin/users')).toBe('#')
    expect(safePreviewHref('/%2561dmin')).toBe('#')
  })
})
