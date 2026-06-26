import { afterEach, describe, expect, it, vi } from 'vitest'

const VISITOR_ID_KEY = 'blog.public.visitor.id.v1'
const VISITOR_ID_COOKIE = 'blog_public_visitor_id_v1'

describe('getVisitorFingerprint', () => {
  afterEach(() => {
    window.localStorage.clear()
    document.cookie = `${VISITOR_ID_COOKIE}=; Path=/; Max-Age=0`
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('restores the visitor id from cookie when local storage is unavailable', async () => {
    stubStableBrowserSignals()
    window.localStorage.setItem(VISITOR_ID_KEY, 'a'.repeat(48))
    const firstModule = await import('./visitorFingerprint.ts')
    const first = await firstModule.getVisitorFingerprint()

    vi.resetModules()
    window.localStorage.clear()
    const secondModule = await import('./visitorFingerprint.ts')
    const second = await secondModule.getVisitorFingerprint()

    expect(first.visitor_id).toBe(second.visitor_id)
    expect(first.browser_hash).toBe(second.browser_hash)
    expect(first.device_hash).toBe(second.device_hash)
    expect(first.composite_hash).toBe(second.composite_hash)
    expect(window.localStorage.getItem(VISITOR_ID_KEY)).toBe(first.visitor_id)
  })

  it('prefers the cookie visitor id when local storage has drifted', async () => {
    stubStableBrowserSignals()
    window.localStorage.setItem(VISITOR_ID_KEY, 'a'.repeat(48))
    const firstModule = await import('./visitorFingerprint.ts')
    const first = await firstModule.getVisitorFingerprint()

    vi.resetModules()
    window.localStorage.setItem(VISITOR_ID_KEY, 'b'.repeat(48))
    const secondModule = await import('./visitorFingerprint.ts')
    const second = await secondModule.getVisitorFingerprint()

    expect(second.visitor_id).toBe(first.visitor_id)
    expect(second.composite_hash).toBe(first.composite_hash)
    expect(window.localStorage.getItem(VISITOR_ID_KEY)).toBe(first.visitor_id)
  })

  it('provides a stable fallback fingerprint for the previous frontend identity', async () => {
    stubStableBrowserSignals()
    window.localStorage.setItem(VISITOR_ID_KEY, 'a'.repeat(48))
    const module = await import('./visitorFingerprint.ts')

    const primary = await module.getVisitorFingerprint()
    const fallback = await module.getStableVisitorFingerprintFallback()

    expect(fallback.visitor_id).toBe(primary.visitor_id)
    expect(fallback.browser_hash).toBe(primary.browser_hash)
    expect(fallback.device_hash).toBe(primary.device_hash)
    expect(fallback.composite_hash).not.toBe(primary.composite_hash)
  })
})

function stubStableBrowserSignals() {
  vi.spyOn(Intl, 'DateTimeFormat').mockReturnValue({
    resolvedOptions: () => ({ timeZone: 'Asia/Shanghai' }),
  } as Intl.DateTimeFormat)
  vi.stubGlobal(
    'screen',
    {
      width: 1536,
      height: 864,
      colorDepth: 24,
    } satisfies Partial<Screen>,
  )
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
    (contextId: string) => {
      if (contextId === '2d') {
        return {
          set textBaseline(_value: string) {},
          set font(_value: string) {},
          set fillStyle(_value: string) {},
          set strokeStyle(_value: string) {},
          fillRect: vi.fn(),
          fillText: vi.fn(),
          beginPath: vi.fn(),
          arc: vi.fn(),
          stroke: vi.fn(),
        } as unknown as CanvasRenderingContext2D
      }
      return {
        VENDOR: 0x1f00,
        RENDERER: 0x1f01,
        getExtension: vi.fn(() => null),
        getParameter: vi.fn((parameter: number) =>
          parameter === 0x1f00 ? 'stable-vendor' : 'stable-renderer',
        ),
      } as unknown as WebGLRenderingContext
    },
  )
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(
    'data:image/png;base64,stable-canvas',
  )
  class StableAudioContext {
    sampleRate = 48000

    close() {
      return Promise.resolve()
    }
  }
  vi.stubGlobal('AudioContext', StableAudioContext)
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: 'zh-CN',
  })
  Object.defineProperty(window.navigator, 'languages', {
    configurable: true,
    value: ['zh-CN', 'zh'],
  })
  Object.defineProperty(window.navigator, 'platform', {
    configurable: true,
    value: 'Win32',
  })
  Object.defineProperty(window.navigator, 'hardwareConcurrency', {
    configurable: true,
    value: 8,
  })
  Object.defineProperty(window.navigator, 'maxTouchPoints', {
    configurable: true,
    value: 0,
  })
}
