import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type FetchResolve = (response: Response) => void
type MockSaltSocketInstance = EventTarget & {
  readonly url: string
  readyState: number
  sentPayloads: unknown[]
  close: () => void
  closeWithCode: (code: number) => void
}

let restoreDocumentCookie: (() => void) | undefined
const saltSessionScopes = new Map<string, 'admin' | 'public'>()
let saltWebSocketInstances: MockSaltSocketInstance[] = []
let saltWebSocketRespondToPing = true
let saltWebSocketCloseCodeOnSaltRequest: number | null = null
let saltWebSocketCloseAfterSaltRequests: number | null = null
let saltWebSocketSaltRequestCount = 0

describe('getEncryptionSession', () => {
  beforeEach(() => {
    vi.resetModules()
    saltSessionScopes.clear()
    saltWebSocketInstances = []
    saltWebSocketRespondToPing = true
    saltWebSocketCloseCodeOnSaltRequest = null
    saltWebSocketCloseAfterSaltRequests = null
    saltWebSocketSaltRequestCount = 0
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
          context_seed: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
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
    expect(cookieWrites).toHaveLength(0)
  })

  it('does not rewrite esid cookies just for cached request headers', async () => {
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
            context_seed: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
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

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const publicSession = await getEncryptionSession('content-v1', 'public')
    await createEncryptionRequestHeaders(publicSession, 'content-v1')
    const adminSession = await getEncryptionSession('sensitive-v1', 'admin')
    await createEncryptionRequestHeaders(adminSession, 'sensitive-v1')
    await createEncryptionRequestHeaders(publicSession, 'content-v1')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(cookieWrites).toHaveLength(2)
    expect(cookieWrites[0]).toContain('Path=/api/public')
    expect(cookieWrites[1]).toContain('Path=/api/admin')
  })

  it('keeps esid cookie stable while issuing one-time esid salts', async () => {
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

    expect(firstHeaders['X-Encryption-Esid-Salt']).toBe('lease-1')
    expect(secondHeaders['X-Encryption-Esid-Salt']).toBe('lease-3')
    expect(cookieWrites).toHaveLength(1)
    const publicEsid = readCookieValue(cookieWrites[0])
    expect(publicEsid).toBeTruthy()
    expect(publicEsid.length).toBeLessThan(ESID_COOKIE_SIZE_LIMIT)
  })

  it('opens the salt websocket before creating the esid cookie', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    const cookieWrites = captureCookieWrites()
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))
    vi.mocked(crypto.subtle.sign).mockRejectedValueOnce(
      new Error('esid signing failed'),
    )

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    await expect(
      createEncryptionRequestHeaders(session, 'content-v1'),
    ).rejects.toThrow('esid signing failed')

    expect(saltWebSocketInstances).toHaveLength(1)
    expect(saltWebSocketInstances[0]?.sentPayloads).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          kind: 'salt_batch_request',
          items: expect.arrayContaining([
            expect.objectContaining({ purpose: 'esid' }),
            expect.objectContaining({ purpose: 'response' }),
          ]),
        }),
      ]),
    )
    expect(cookieWrites).toHaveLength(0)
  })

  it('shares one opening salt websocket across concurrent requests', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    await Promise.all([
      createEncryptionRequestHeaders(session, 'content-v1'),
      createEncryptionRequestHeaders(session, 'content-v1'),
    ])

    expect(saltWebSocketInstances).toHaveLength(1)
  })

  it('keeps the salt websocket alive with encrypted heartbeat pongs', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    await createEncryptionRequestHeaders(session, 'content-v1')
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

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    await createEncryptionRequestHeaders(session, 'content-v1')
    const firstSocket = saltWebSocketInstances[0]
    expect(firstSocket).toBeDefined()

    await vi.advanceTimersByTimeAsync(75_000)
    expect(firstSocket?.readyState).toBe(WebSocket.CLOSED)

    await vi.advanceTimersByTimeAsync(1_000)

    expect(saltWebSocketInstances.length).toBeGreaterThan(1)
    expect(saltWebSocketInstances.at(-1)?.readyState).toBe(WebSocket.OPEN)
  })

  it('does not reconnect the salt websocket after policy close', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    vi.spyOn(Math, 'random').mockReturnValue(0)
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    saltWebSocketCloseCodeOnSaltRequest = 1008
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    const request = createEncryptionRequestHeaders(session, 'content-v1')
    await expect(request).rejects.toThrow('salt lease socket closed by policy')

    await vi.advanceTimersByTimeAsync(30_000)

    expect(saltWebSocketInstances).toHaveLength(1)
  })

  it('maps salt policy closes to a public rate-limit api error', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    saltWebSocketCloseCodeOnSaltRequest = 1008
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { apiGetEncrypted } = await import('./client.ts')

    await expect(
      apiGetEncrypted('/public/posts?limit=1&offset=0', 'content-v1', {
        encryptionScope: 'public',
      }),
    ).rejects.toMatchObject({
      message: '您的访问太频繁，请稍后重试',
      status: 429,
    })
  })

  it('maps public encryption session rate limits to a public rate-limit api error', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    const fetchMock = vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: 'Too many attempts' }), {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
          },
        }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { apiGetEncrypted } = await import('./client.ts')

    await expect(
      apiGetEncrypted('/public/posts?limit=1&offset=0', 'content-v1', {
        encryptionScope: 'public',
      }),
    ).rejects.toMatchObject({
      message: '您的访问太频繁，请稍后重试',
      status: 429,
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(saltWebSocketInstances).toHaveLength(0)
  })

  it('blocks queued salt requests during policy cooldown without opening more websockets', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    saltWebSocketCloseCodeOnSaltRequest = 1008
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    const results = await Promise.allSettled([
      createEncryptionRequestHeaders(session, 'content-v1'),
      createEncryptionRequestHeaders(session, 'content-v1'),
      createEncryptionRequestHeaders(session, 'content-v1'),
    ])

    expect(results).toHaveLength(3)
    expect(results.every((result) => result.status === 'rejected')).toBe(true)
    expect(
      results.map((result) =>
        result.status === 'rejected' ? String(result.reason) : '',
      ),
    ).toEqual([
      expect.stringContaining('policy'),
      expect.stringContaining('policy'),
      expect.stringContaining('policy'),
    ])
    expect(saltWebSocketInstances).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(999)
    await expect(
      createEncryptionRequestHeaders(session, 'content-v1'),
    ).rejects.toThrow('temporarily blocked by policy')
    expect(saltWebSocketInstances).toHaveLength(1)

    saltWebSocketCloseCodeOnSaltRequest = null
    await vi.advanceTimersByTimeAsync(2)
    await expect(
      createEncryptionRequestHeaders(session, 'content-v1'),
    ).resolves.toEqual(
      expect.objectContaining({
        'X-Encryption-Session': 'public-session',
      }),
    )
    expect(saltWebSocketInstances).toHaveLength(2)
  })

  it('uses the remaining local salt message window for policy cooldown', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/')
    captureCookieWrites()
    saltWebSocketCloseAfterSaltRequests = 31
    vi.stubGlobal('fetch', sessionFetchMock('public-session', 'public'))

    const { createEncryptionRequestHeaders, getEncryptionSession } = await import(
      './encryption.ts'
    )

    const session = await getEncryptionSession('content-v1', 'public')
    for (let index = 0; index < 30; index += 1) {
      await createEncryptionRequestHeaders(session, 'content-v1')
      await vi.advanceTimersByTimeAsync(1_000)
    }
    await expect(
      createEncryptionRequestHeaders(session, 'content-v1'),
    ).rejects.toThrow('salt lease socket closed by policy')
    expect(saltWebSocketInstances).toHaveLength(1)

    saltWebSocketCloseAfterSaltRequests = null
    await vi.advanceTimersByTimeAsync(29_000)
    await expect(
      createEncryptionRequestHeaders(session, 'content-v1'),
    ).rejects.toThrow('temporarily blocked by policy')
    expect(saltWebSocketInstances).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(1_251)
    await expect(
      createEncryptionRequestHeaders(session, 'content-v1'),
    ).resolves.toEqual(
      expect.objectContaining({
        'X-Encryption-Session': 'public-session',
      }),
    )
    expect(saltWebSocketInstances).toHaveLength(2)
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

const ESID_COOKIE_SIZE_LIMIT = 512

function readCookieValue(cookieWrite: string): string {
  const value = cookieWrite.split(';')[0]?.split('=').slice(1).join('=') ?? ''
  return decodeURIComponent(value)
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
      digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer),
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
    leaseCounter = 0

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
      saltWebSocketSaltRequestCount += 1
      if (
        saltWebSocketCloseAfterSaltRequests !== null &&
        saltWebSocketSaltRequestCount >= saltWebSocketCloseAfterSaltRequests
      ) {
        this.closeWithCode(1008)
        return
      }
      if (saltWebSocketCloseCodeOnSaltRequest !== null) {
        this.closeWithCode(saltWebSocketCloseCodeOnSaltRequest)
        return
      }
      queueMicrotask(() => {
        const scope = this.url.includes('/admin/') ? 'admin' : 'public'
        const requests = saltLeaseRequestsFromPayload(payload)
        this.dispatchEvent(
          new MessageEvent('message', {
            data: JSON.stringify({
              type: 'salt_leases',
              frames: requests.map((request) => {
                this.leaseCounter += 1
                return encodeFramePayload(frame.session_id, {
                  lease_id: `lease-${this.leaseCounter}`,
                  purpose: request.purpose,
                  scope,
                  profile: request.profile,
                  salt: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
                  expires_at: 4_071_398_400,
                })
              }),
            }),
          }),
        )
      })
    }

    close(): void {
      this.closeWithCode(1000)
    }

    closeWithCode(code: number): void {
      this.readyState = MockWebSocket.CLOSED
      this.dispatchEvent(new CloseEvent('close', { code }))
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
          context_seed: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
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
  count: number
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

function isSaltBatchRequestPayload(value: unknown): value is {
  kind: 'salt_batch_request'
  items: Array<{
    purpose: 'esid' | 'login_capsule' | 'request' | 'response'
    profile: 'sensitive-v1' | 'content-v1' | null
    count: number
  }>
} {
  if (!value || typeof value !== 'object') {
    return false
  }
  const payload = value as { kind?: unknown; items?: unknown }
  return payload.kind === 'salt_batch_request' && Array.isArray(payload.items)
}

function saltLeaseRequestsFromPayload(value: unknown): Array<{
  purpose: 'esid' | 'login_capsule' | 'request' | 'response'
  profile: 'sensitive-v1' | 'content-v1' | null
}> {
  if (isSaltBatchRequestPayload(value)) {
    return value.items.flatMap((item) =>
      Array.from({ length: item.count }, () => ({
        purpose: item.purpose,
        profile: item.profile,
      })),
    )
  }
  if (isSaltRequestPayload(value)) {
    return Array.from({ length: value.count }, () => ({
      purpose: value.purpose,
      profile: value.profile,
    }))
  }
  return [{ purpose: 'esid', profile: null }]
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
