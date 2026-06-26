import type { VisitorFingerprint } from './types.ts'

const VISITOR_ID_KEY = 'blog.public.visitor.id.v1'
const VISITOR_ID_COOKIE = 'blog_public_visitor_id_v1'
const VISITOR_ID_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 2
const FINGERPRINT_VERSION = 'web-v1'

let cachedFingerprint: Promise<VisitorFingerprint> | null = null

export function getVisitorFingerprint(): Promise<VisitorFingerprint> {
  cachedFingerprint ??= createVisitorFingerprint()
  return cachedFingerprint
}

export async function getStableVisitorFingerprintFallback(): Promise<VisitorFingerprint> {
  const fingerprint = await getVisitorFingerprint()
  return {
    ...fingerprint,
    composite_hash: await createCompositeHash({
      browserHash: fingerprint.browser_hash,
      deviceHash: fingerprint.device_hash,
      language: fingerprint.language,
      platform: fingerprint.platform,
      screenValue: fingerprint.screen,
      timezone: fingerprint.timezone,
      visitorId: null,
    }),
    created_at_ms: Date.now(),
  }
}

async function createVisitorFingerprint(): Promise<VisitorFingerprint> {
  const visitorId = getOrCreateVisitorId()
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone ?? null
  const language = navigator.language || null
  const platform = navigator.platform || null
  const screenValue = screen
    ? `${screen.width}x${screen.height}x${screen.colorDepth}`
    : null

  const navigatorWithMemory = navigator as Navigator & {
    deviceMemory?: number
  }
  const browserSignals = [
    navigator.userAgent,
    language,
    navigator.languages?.join(',') ?? '',
    timezone,
    platform,
    String(navigator.hardwareConcurrency ?? ''),
    String(navigatorWithMemory.deviceMemory ?? ''),
    String(navigator.maxTouchPoints ?? ''),
  ]
  const deviceSignals = [
    screenValue,
    canvasSignal(),
    webglSignal(),
    await audioSignal(),
  ]

  const browserHash = await sha256Hex(browserSignals.join('|'))
  const deviceHash = await sha256Hex(deviceSignals.join('|'))
  const compositeHash = await createCompositeHash({
    visitorId,
    browserHash,
    deviceHash,
    timezone,
    language,
    platform,
    screenValue,
  })

  return {
    version: FINGERPRINT_VERSION,
    visitor_id: visitorId,
    browser_hash: browserHash,
    device_hash: deviceHash,
    composite_hash: compositeHash,
    timezone,
    language,
    platform,
    screen: screenValue,
    created_at_ms: Date.now(),
  }
}

async function createCompositeHash({
  visitorId,
  browserHash,
  deviceHash,
  timezone,
  language,
  platform,
  screenValue,
}: {
  visitorId: string | null
  browserHash: string
  deviceHash: string
  timezone: string | null
  language: string | null
  platform: string | null
  screenValue: string | null
}): Promise<string> {
  const parts =
    visitorId === null
      ? [
          FINGERPRINT_VERSION,
          browserHash,
          deviceHash,
          timezone,
          language,
          platform,
          screenValue,
        ]
      : [
          FINGERPRINT_VERSION,
          visitorId,
          browserHash,
          deviceHash,
          timezone,
          language,
          platform,
          screenValue,
        ]
  return sha256Hex(parts.join('|'))
}

function getOrCreateVisitorId(): string {
  const localVisitorId = readLocalVisitorId()
  const cookieVisitorId = readVisitorIdCookie()
  if (cookieVisitorId) {
    writeVisitorId(cookieVisitorId)
    return cookieVisitorId
  }
  if (localVisitorId) {
    writeVisitorId(localVisitorId)
    return localVisitorId
  }
  const next = randomId()
  writeVisitorId(next)
  return next
}

function readLocalVisitorId(): string | null {
  try {
    const existing = window.localStorage.getItem(VISITOR_ID_KEY)
    if (isVisitorId(existing)) {
      return existing
    }
  } catch {
    return null
  }
  return null
}

function writeVisitorId(value: string) {
  try {
    window.localStorage.setItem(VISITOR_ID_KEY, value)
  } catch {
    // Ignore storage failures; the cookie fallback can still carry the identity.
  }
  writeVisitorIdCookie(value)
}

function readVisitorIdCookie(): string | null {
  const prefix = `${VISITOR_ID_COOKIE}=`
  const value = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix))
    ?.slice(prefix.length)
  return isVisitorId(value) ? value : null
}

function isVisitorId(value: string | null | undefined): value is string {
  return (
    typeof value === 'string' &&
    value.length >= 16 &&
    value.length <= 128 &&
    /^[a-f0-9]+$/i.test(value)
  )
}

function writeVisitorIdCookie(value: string) {
  document.cookie = [
    `${VISITOR_ID_COOKIE}=${value}`,
    'Path=/',
    `Max-Age=${VISITOR_ID_MAX_AGE_SECONDS}`,
    'SameSite=Lax',
    location.protocol === 'https:' ? 'Secure' : '',
  ]
    .filter(Boolean)
    .join('; ')
}

function randomId(): string {
  const bytes = new Uint8Array(24)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

function canvasSignal(): string {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 240
    canvas.height = 80
    const context = canvas.getContext('2d')
    if (!context) {
      return 'canvas:none'
    }
    context.textBaseline = 'top'
    context.font = '16px serif'
    context.fillStyle = '#f7f3ec'
    context.fillRect(0, 0, 240, 80)
    context.fillStyle = '#453f39'
    context.fillText('blog fingerprint 2026', 12, 18)
    context.strokeStyle = '#b97a8a'
    context.beginPath()
    context.arc(128, 42, 18, 0, Math.PI * 1.7)
    context.stroke()
    return canvas.toDataURL()
  } catch {
    return 'canvas:error'
  }
}

function webglSignal(): string {
  try {
    const canvas = document.createElement('canvas')
    const context =
      canvas.getContext('webgl') ?? canvas.getContext('experimental-webgl')
    if (!context) {
      return 'webgl:none'
    }
    const gl = context as WebGLRenderingContext
    const extension = gl.getExtension('WEBGL_debug_renderer_info')
    const vendor = extension
      ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL)
      : gl.getParameter(gl.VENDOR)
    const renderer = extension
      ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL)
      : gl.getParameter(gl.RENDERER)
    return `${String(vendor)}|${String(renderer)}`
  } catch {
    return 'webgl:error'
  }
}

async function audioSignal(): Promise<string> {
  try {
    const AudioContextClass = window.AudioContext ?? window.webkitAudioContext
    if (!AudioContextClass) {
      return 'audio:none'
    }
    const context = new AudioContextClass()
    const value = String(context.sampleRate)
    await context.close()
    return value
  } catch {
    return 'audio:error'
  }
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

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext
  }
}
