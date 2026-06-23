import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type FetchResolve = (response: Response) => void
type MockSaltSocketInstance = EventTarget & {
  readonly url: string
  readyState: number
  sentPayloads: unknown[]
  close: () => void
}

let restoreDocumentCookie: (() => void) | undefined
const saltSessionScopes = new Map<string, 'admin' | 'public'>()
let saltWebSocketInstances: MockSaltSocketInstance[] = []
let saltWebSocketRespondToPing = true

describe('getEncryptionSession', () => {
  beforeEach(() => {
    vi.resetModules()
    saltSessionScopes.clear()
    saltWebSocketInstances = []
    saltWebSocketRespondToPing = true
    vi.useFakeTimers()
    stubBrowserCrypto()
    stubSaltWebSocket()
  })

  afterEach(() => {
    restoreDocumentCookie?.()
    restoreDocumentCookie = undefined
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('keeps shared session negotiation alive when one caller aborts', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/api/test')
    const cookieWrites = captureCookieWrites()
    let resolveFetch: FetchResolve | undefined
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve
    })
    const fetchMock = vi.fn<typeof fetch>(() => fetchPromise)
    vi.stubGlobal('fetch', fetchMock)

    const { getEncryptionSession } = await import('./encryption.ts')

    const firstController = new AbortController()
    const secondController = new AbortController()
    const firstSession = getEncryptionSession(
      'content-v1',
      'public',
      firstController.signal,
    )
    const firstResult = expect(firstSession).rejects.toMatchObject({
      name: 'AbortError',
    })
    const secondSession = getEncryptionSession(
      'content-v1',
      'public',
      secondController.signal,
    )

    firstController.abort()

    await firstResult
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty('signal')

    resolveFetch?.(
      new Response(
        JSON.stringify({
          session_id: 'session-1',
          scope: 'public',
          server_public_key: {
            kty: 'EC',
            crv: 'P-256',
            x: 'server-x',
            y: 'server-y',
          },
          profiles: ['content-v1'],
          expires_at: '2099-01-01T00:00:00Z',
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    )

    await expect(secondSession).resolves.toMatchObject({
      id: 'session-1',
      scope: 'public',
      profiles: ['content-v1'],
    })
    expect(document.cookie).toContain('esid=')
    expect(cookieWrites.at(-1)).toContain('Path=/api/public')
  })

  it('does not rewrite esid cookies just for cached session reuse', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    const cookieWrites = captureCookieWrites()
    const fetchMock = vi.fn<typeof fetch>((input) => {
      const url = String(input)
      const scope = url.includes('/admin/') ? 'admin' : 'public'
      return Promise.resolve(
        new Response(
          JSON.stringify({
            session_id: `${scope}-session`,
            scope,
            server_public_key: {
              kty: 'EC',
              crv: 'P-256',
              x: 'server-x',
              y: 'server-y',
            },
            profiles:
              scope === 'admin' ? ['sensitive-v1', 'content-v1'] : ['content-v1'],
            expires_at: '2099-01-01T00:00:00Z',
          }),
          {
            status: 200,
            headers: {
              'Content-Type': 'application/json',
            },
          },
        ),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const { getEncryptionSession } = await import('./encryption.ts')

    await getEncryptionSession('content-v1', 'public')
    await getEncryptionSession('sensitive-v1', 'admin')
    await getEncryptionSession('content-v1', 'public')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(cookieWrites).toHaveLength(2)
    expect(cookieWrites[0]).toContain('Path=/api/public')
    expect(cookieWrites[1]).toContain('Path=/api/admin')
  })

  it('keeps multiple in-flight esids in one scoped cookie bundle', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    const cookieWrites = captureCookieWrites()
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    const firstHeaders = await createEncryptionRequestHeaders(session, 'content-v1')
    const secondHeaders = await createEncryptionRequestHeaders(session, 'content-v1')

    expect(firstHeaders['X-Encryption-Esid-Salt']).toBe('lease-2')
    expect(secondHeaders['X-Encryption-Esid-Salt']).toBe('lease-4')
    const publicBundle = decodeCookieBundle(cookieWrites.at(-1) ?? '')
    expect(publicBundle.session_id).toBe('public-session')
    expect(publicBundle.scope).toBe('public')
    expect(publicBundle.items).toHaveLength(3)
    expect(publicBundle.items.map(([saltId]) => saltId)).toEqual([
      'lease-1',
      'lease-2',
      'lease-4',
    ])
  })

  it('keeps the salt websocket alive with encrypted heartbeat pongs', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { getEncryptionSession } = await import('./encryption.ts')

    await getEncryptionSession('content-v1', 'public')
    const socket = saltWebSocketInstances[0]
    expect(socket).toBeDefined()

    await vi.advanceTimersByTimeAsync(25_000)

    expect(socket?.sentPayloads).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          kind: 'ping',
          seq: 1,
        }),
      ]),
    )
    expect(socket?.readyState).toBe(WebSocket.OPEN)
  })

  it('reconnects the salt websocket after missed heartbeat pongs', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    vi.spyOn(Math, 'random').mockReturnValue(0)
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    saltWebSocketRespondToPing = false
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { getEncryptionSession } = await import('./encryption.ts')

    await getEncryptionSession('content-v1', 'public')
    const firstSocket = saltWebSocketInstances[0]
    expect(firstSocket).toBeDefined()

    await vi.advanceTimersByTimeAsync(75_000)
    expect(firstSocket?.readyState).toBe(WebSocket.CLOSED)

    await vi.advanceTimersByTimeAsync(1_000)

    expect(saltWebSocketInstances.length).toBeGreaterThan(1)
    expect(saltWebSocketInstances.at(-1)?.readyState).toBe(WebSocket.OPEN)
  })
})

function captureCookieWrites(): string[] {
  const writes: string[] = []
  const originalDescriptor = Object.getOwnPropertyDescriptor(document, 'cookie')
  let cookieValue = ''

  Object.defineProperty(document, 'cookie', {
    configurable: true,
    get: () => cookieValue,
    set: (value: string) => {
      cookieValue = value
      writes.push(value)
    },
  })
  restoreDocumentCookie = () => {
    if (originalDescriptor) {
      Object.defineProperty(document, 'cookie', originalDescriptor)
      return
    }
    delete (document as { cookie?: string }).cookie
  }
  return writes
}

function decodeCookieBundle(cookieWrite: string): {
  session_id: string
  scope: string
  items: [string, string][]
} {
  const value = cookieWrite.split(';')[0]?.split('=').slice(1).join('=') ?? ''
  return JSON.parse(
    new TextDecoder().decode(base64urlDecode(decodeURIComponent(value))),
  ) as {
    session_id: string
    scope: string
    items: [string, string][]
  }
}

function stubBrowserCrypto(): void {
  const keyPair = {
    privateKey: {} as CryptoKey,
    publicKey: {} as CryptoKey,
  }
  const sharedSecret = new Uint8Array(32)

  vi.stubGlobal('crypto', {
    subtle: {
      decrypt: vi.fn().mockImplementation((_: AesGcmParams, __, data) => {
        return Promise.resolve(toArrayBuffer(data))
      }),
      deriveBits: vi.fn().mockResolvedValue(sharedSecret.buffer),
      deriveKey: vi.fn().mockResolvedValue({} as CryptoKey),
      encrypt: vi.fn().mockImplementation((_: AesGcmParams, __, data) => {
        return Promise.resolve(toArrayBuffer(data))
      }),
      exportKey: vi.fn().mockResolvedValue({
        kty: 'EC',
        crv: 'P-256',
        x: 'client-x',
        y: 'client-y',
      }),
      generateKey: vi.fn().mockResolvedValue(keyPair),
      importKey: vi.fn().mockResolvedValue({} as CryptoKey),
      sign: vi.fn().mockResolvedValue(new Uint8Array(32).buffer),
    },
    getRandomValues: <T extends ArrayBufferView | null>(array: T): T => array,
  } as unknown as Crypto)
}

function stubSaltWebSocket(): void {
  class MockWebSocket extends EventTarget {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3
    readyState = MockWebSocket.CONNECTING
    readonly url: string
    sentPayloads: unknown[] = []

    constructor(url: string) {
      super()
      this.url = url
      saltWebSocketInstances.push(this)
      queueMicrotask(() => {
        this.readyState = MockWebSocket.OPEN
        this.dispatchEvent(new Event('open'))
      })
    }

    send(data: string): void {
      const frame = JSON.parse(data) as {
        session_id: string
        ciphertext: string
      }
      const payload = decodeFramePayload(frame)
      this.sentPayloads.push(payload)
      saltSessionScopes.set(
        frame.session_id,
        this.url.includes('/admin/') ? 'admin' : 'public',
      )
      if (isPingPayload(payload)) {
        if (!saltWebSocketRespondToPing) {
          return
        }
        queueMicrotask(() => {
          this.dispatchEvent(
            new MessageEvent('message', {
              data: JSON.stringify({
                type: 'pong',
                frame: encodeFramePayload(frame.session_id, {
                  kind: 'pong',
                  seq: payload.seq,
                  ts: payload.ts,
                }),
              }),
            }),
          )
        })
        return
      }
      queueMicrotask(() => {
        const scope = this.url.includes('/admin/') ? 'admin' : 'public'
        this.dispatchEvent(
          new MessageEvent('message', {
            data: JSON.stringify({
              type: 'salt_leases',
              frames: [
                encodeFramePayload(frame.session_id, {
                  lease_id: `lease-${this.sentPayloads.length}`,
                  purpose: isSaltRequestPayload(payload) ? payload.purpose : 'esid',
                  scope,
                  profile: isSaltRequestPayload(payload) ? payload.profile : null,
                  salt: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
                  expires_at: 4_071_398_400,
                }),
              ],
            }),
          }),
        )
      })
    }

    close(): void {
      this.readyState = MockWebSocket.CLOSED
      this.dispatchEvent(new Event('close'))
    }
  }

  vi.stubGlobal('WebSocket', MockWebSocket)
}

function sessionFetchMock(
  sessionId: string,
  scope: 'admin' | 'public',
): typeof fetch {
  return vi.fn<typeof fetch>(() =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          session_id: sessionId,
          scope,
          server_public_key: {
            kty: 'EC',
            crv: 'P-256',
            x: 'server-x',
            y: 'server-y',
          },
          profiles: scope === 'admin' ? ['sensitive-v1', 'content-v1'] : ['content-v1'],
          expires_at: '2099-01-01T00:00:00Z',
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    ),
  )
}

function isPingPayload(value: unknown): value is { kind: 'ping'; seq: number; ts: number } {
  if (!value || typeof value !== 'object') {
    return false
  }
  const payload = value as { kind?: unknown; seq?: unknown; ts?: unknown }
  return (
    payload.kind === 'ping' &&
    typeof payload.seq === 'number' &&
    typeof payload.ts === 'number'
  )
}

function isSaltRequestPayload(value: unknown): value is {
  kind: 'salt_request'
  purpose: 'esid' | 'login_capsule' | 'request' | 'response'
  profile: 'sensitive-v1' | 'content-v1' | null
} {
  if (!value || typeof value !== 'object') {
    return false
  }
  const payload = value as { kind?: unknown; purpose?: unknown; profile?: unknown }
  return (
    payload.kind === 'salt_request' &&
    typeof payload.purpose === 'string' &&
    (payload.profile === null || typeof payload.profile === 'string')
  )
}

function encodeFramePayload(
  sessionId: string,
  payload: Record<string, unknown>,
): {
  session_id: string
  wrap_salt: string
  nonce: string
  ciphertext: string
} {
  return {
    session_id: sessionId,
    wrap_salt: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    nonce: 'AAAAAAAAAAAAAAAA',
    ciphertext: base64urlEncode(new TextEncoder().encode(JSON.stringify(payload))),
  }
}

function decodeFramePayload(frame: { ciphertext: string }): unknown {
  return JSON.parse(new TextDecoder().decode(base64urlDecode(frame.ciphertext)))
}

function toArrayBuffer(data: BufferSource): ArrayBuffer {
  const bytes =
    data instanceof ArrayBuffer
      ? new Uint8Array(data)
      : new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
  const output = new ArrayBuffer(bytes.byteLength)
  new Uint8Array(output).set(bytes)
  return output
}

function base64urlEncode(value: Uint8Array): string {
  const binary = Array.from(value, (byte) => String.fromCharCode(byte)).join('')
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function base64urlDecode(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = `${base64}${'='.repeat((4 - (base64.length % 4)) % 4)}`
  const binary = atob(padded)
  return toArrayBuffer(Uint8Array.from(binary, (char) => char.charCodeAt(0)))
}
