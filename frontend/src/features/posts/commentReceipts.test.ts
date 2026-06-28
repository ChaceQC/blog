import { afterEach, describe, expect, it, vi } from 'vitest'

const AUTHOR_SECRET_KEY = 'blog.public.comment.author_secret.v1'
const RECEIPTS_KEY = 'blog.public.comment.receipts.v1'
const AUTHOR_SECRET_COOKIE = 'blog_public_comment_author_secret_v1'

describe('comment receipts', () => {
  afterEach(() => {
    window.localStorage.clear()
    document.cookie = `${AUTHOR_SECRET_COOKIE}=; Path=/; Max-Age=0`
    vi.restoreAllMocks()
    vi.resetModules()
  })

  it('persists a receipt so pending comments can be restored after refresh', async () => {
    const module = await import('./commentReceipts.ts')
    const saved = module.saveCommentReceipt({
      comment_id: 12,
      post_slug: 'public-post',
      delete_token: 'delete-token-value-with-enough-length-123456',
      created_at: '2026-06-29T00:00:00.000Z',
    })

    vi.resetModules()
    const refreshedModule = await import('./commentReceipts.ts')

    expect(saved).toBe(true)
    expect(refreshedModule.receiptPayload('public-post')).toEqual([
      {
        comment_id: 12,
        post_slug: 'public-post',
        delete_token: 'delete-token-value-with-enough-length-123456',
      },
    ])
    expect(refreshedModule.hasCommentReceipt(12, 'public-post')).toBe(true)
  })

  it('ignores tampered receipts from local storage', async () => {
    window.localStorage.setItem(
      RECEIPTS_KEY,
      JSON.stringify([
        {
          comment_id: 13,
          post_slug: 'public-post',
          delete_token: 'bad token with spaces',
          created_at: '2026-06-29T00:00:00.000Z',
        },
        {
          comment_id: 14,
          post_slug: '../other-post',
          delete_token: 'delete-token-value-with-enough-length-abcdef',
          created_at: '2026-06-29T00:00:00.000Z',
        },
      ]),
    )
    const module = await import('./commentReceipts.ts')

    expect(module.receiptPayload('public-post')).toEqual([])
    expect(module.receiptToken(13, 'public-post')).toBeNull()
  })

  it('uses cookie author secret to recover the same proof when storage drifts', async () => {
    window.localStorage.setItem(AUTHOR_SECRET_KEY, 'a'.repeat(64))
    const firstModule = await import('./commentReceipts.ts')
    const firstProof = await firstModule.getCommentAuthorSecretProof()

    vi.resetModules()
    window.localStorage.setItem(AUTHOR_SECRET_KEY, 'b'.repeat(64))
    const secondModule = await import('./commentReceipts.ts')
    const secondProof = await secondModule.getCommentAuthorSecretProof()

    expect(secondProof).toBe(firstProof)
    expect(window.localStorage.getItem(AUTHOR_SECRET_KEY)).toBe('a'.repeat(64))
  })
})
