import type { PublicCommentReceipt } from './types.ts'

const AUTHOR_SECRET_KEY = 'blog.public.comment.author_secret.v1'
const RECEIPTS_KEY = 'blog.public.comment.receipts.v1'
const AUTHOR_SECRET_COOKIE = 'blog_public_comment_author_secret_v1'
const MAX_RECEIPTS = 200
const AUTHOR_SECRET_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 2
const SLUG_PATTERN = /^[a-z0-9][a-z0-9_-]*$/
const DELETE_TOKEN_PATTERN = /^[A-Za-z0-9_-]+$/

export async function getCommentAuthorSecretProof(): Promise<string> {
  return sha256Hex(getOrCreateAuthorSecret())
}

export function readCommentReceipts(postSlug?: string): PublicCommentReceipt[] {
  const raw = readReceiptStore()
  const receipts = raw.filter(isValidReceipt)
  if (postSlug) {
    return receipts.filter((receipt) => receipt.post_slug === postSlug)
  }
  return receipts
}

export function saveCommentReceipt(receipt: PublicCommentReceipt): boolean {
  if (!isValidReceipt(receipt)) {
    return false
  }
  const receipts = readCommentReceipts()
    .filter((item) => item.comment_id !== receipt.comment_id)
    .concat(receipt)
    .slice(-MAX_RECEIPTS)
  return writeReceiptStore(receipts)
}

export function removeCommentReceipt(commentId: number): void {
  const receipts = readCommentReceipts().filter(
    (receipt) => receipt.comment_id !== commentId,
  )
  writeReceiptStore(receipts)
}

export function hasCommentReceipt(commentId: number, postSlug: string): boolean {
  return readCommentReceipts(postSlug).some(
    (receipt) => receipt.comment_id === commentId,
  )
}

export function receiptPayload(postSlug: string) {
  return readCommentReceipts(postSlug).map((receipt) => ({
    comment_id: receipt.comment_id,
    post_slug: receipt.post_slug,
    delete_token: receipt.delete_token,
  }))
}

export function receiptToken(commentId: number, postSlug: string): string | null {
  return (
    readCommentReceipts(postSlug).find(
      (receipt) => receipt.comment_id === commentId,
    )?.delete_token ?? null
  )
}

function getOrCreateAuthorSecret(): string {
  const cookieSecret = readAuthorSecretCookie()
  if (isAuthorSecret(cookieSecret)) {
    writeAuthorSecret(cookieSecret)
    return cookieSecret
  }
  const localSecret = readLocalAuthorSecret()
  if (isAuthorSecret(localSecret)) {
    writeAuthorSecret(localSecret)
    return localSecret
  }
  const next = randomHex(32)
  writeAuthorSecret(next)
  return next
}

function readLocalAuthorSecret(): string | null {
  try {
    return window.localStorage.getItem(AUTHOR_SECRET_KEY)
  } catch {
    return null
  }
}

function writeAuthorSecret(value: string): void {
  try {
    window.localStorage.setItem(AUTHOR_SECRET_KEY, value)
  } catch {
    // localStorage 不可用时 Cookie 仍可作为同源恢复锚点。
  }
  document.cookie = [
    `${AUTHOR_SECRET_COOKIE}=${value}`,
    'Path=/',
    `Max-Age=${AUTHOR_SECRET_MAX_AGE_SECONDS}`,
    'SameSite=Lax',
    location.protocol === 'https:' ? 'Secure' : '',
  ]
    .filter(Boolean)
    .join('; ')
}

function readAuthorSecretCookie(): string | null {
  const prefix = `${AUTHOR_SECRET_COOKIE}=`
  return (
    document.cookie
      .split(';')
      .map((item) => item.trim())
      .find((item) => item.startsWith(prefix))
      ?.slice(prefix.length) ?? null
  )
}

function readReceiptStore(): unknown[] {
  try {
    const raw = window.localStorage.getItem(RECEIPTS_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeReceiptStore(receipts: PublicCommentReceipt[]): boolean {
  try {
    window.localStorage.setItem(RECEIPTS_KEY, JSON.stringify(receipts))
    return true
  } catch {
    // 用户仍能看到本次提交返回的审核中状态；刷新后无法自助找回。
    return false
  }
}

function isValidReceipt(value: unknown): value is PublicCommentReceipt {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const receipt = value as Partial<PublicCommentReceipt>
  return (
    Number.isInteger(receipt.comment_id) &&
    Number(receipt.comment_id) > 0 &&
    typeof receipt.post_slug === 'string' &&
    SLUG_PATTERN.test(receipt.post_slug) &&
    typeof receipt.delete_token === 'string' &&
    receipt.delete_token.length >= 32 &&
    receipt.delete_token.length <= 256 &&
    DELETE_TOKEN_PATTERN.test(receipt.delete_token) &&
    typeof receipt.created_at === 'string' &&
    receipt.created_at.length <= 64
  )
}

function isAuthorSecret(value: string | null | undefined): value is string {
  return (
    typeof value === 'string' &&
    value.length === 64 &&
    /^[a-f0-9]+$/i.test(value)
  )
}

function randomHex(lengthBytes: number): string {
  const bytes = new Uint8Array(lengthBytes)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(value),
  )
  return Array.from(new Uint8Array(digest), (item) =>
    item.toString(16).padStart(2, '0'),
  ).join('')
}
