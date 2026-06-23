import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type FetchResolve = (response: Response) => void

describe('getEncryptionSession', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useFakeTimers()
    stubBrowserCrypto()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('keeps shared session negotiation alive when one caller aborts', async () => {
    vi.setSystemTime(new Date('2026-06-23T00:00:00Z'))
    window.history.replaceState({}, '', '/api/test')
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
  })
})

function stubBrowserCrypto(): void {
  const keyPair = {
    privateKey: {} as CryptoKey,
    publicKey: {} as CryptoKey,
  }
  const sharedSecret = new Uint8Array(32)

  vi.stubGlobal('crypto', {
    subtle: {
      deriveBits: vi.fn().mockResolvedValue(sharedSecret.buffer),
      deriveKey: vi.fn().mockResolvedValue({} as CryptoKey),
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
