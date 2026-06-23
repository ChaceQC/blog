import { API_BASE_URL } from './config.ts'
import { parseApiTime } from '../utils/datetime.ts'

export type {
  EncryptedApiResponse,
  EncryptionProfile,
  EncryptionSaltLease,
  EncryptionScope,
  EncryptionSession,
  LoginChallenge,
} from './encryptionTypes.ts'

import type {
  EncryptedApiResponse,
  EncryptionProfile,
  EncryptionSaltLease,
  EncryptionScope,
  EncryptionSession,
  LoginChallenge,
  SaltPurpose,
} from './encryptionTypes.ts'

type BrowserPublicKey = {
  kty: 'EC'
  crv: 'P-256'
  x: string
  y: string
}

type EncryptionSessionResponse = {
  session_id: string
  scope: EncryptionScope
  server_public_key: BrowserPublicKey
  profiles: EncryptionProfile[]
  expires_at: string
  login_challenge?: LoginChallenge | null
}

const ESID_COOKIE_NAME = 'esid'

const activeSessions = new Map<EncryptionScope, EncryptionSession>()
const pendingSessions = new Map<EncryptionScope, Promise<EncryptionSession>>()
const responseSaltRegistry = new Map<string, EncryptionSaltLease>()

export async function getEncryptionSession(
  profile: EncryptionProfile,
  scope: EncryptionScope = 'admin',
  signal?: AbortSignal,
): Promise<EncryptionSession> {
  const now = Date.now()
  const activeSession = activeSessions.get(scope)
  if (
    activeSession &&
    activeSession.expiresAt - now > 30_000 &&
    activeSession.scope === scope &&
    activeSession.profiles.includes(profile)
  ) {
    return activeSession
  }
  if (signal?.aborted) {
    return Promise.reject(abortError())
  }

  let pendingSession = pendingSessions.get(scope)
  if (!pendingSession) {
    pendingSession = createEncryptionSession(scope)
      .then((session) => {
        activeSessions.set(scope, session)
        return session
      })
      .finally(() => {
        pendingSessions.delete(scope)
      })
    pendingSessions.set(scope, pendingSession)
  }
  return await abortable(pendingSession, signal)
}

export async function createFreshEncryptionSession(
  scope: EncryptionScope,
  signal?: AbortSignal,
): Promise<EncryptionSession> {
  activeSessions.get(scope)?.saltSocket?.close()
  activeSessions.delete(scope)
  pendingSessions.delete(scope)
  if (signal?.aborted) {
    return Promise.reject(abortError())
  }
  const session = await abortable(createEncryptionSession(scope), signal)
  activeSessions.set(scope, session)
  return session
}

export async function decryptEncryptedResponse<T>(
  envelope: EncryptedApiResponse,
  profile: EncryptionProfile,
  session: EncryptionSession,
): Promise<T> {
  const responseSalt = consumeResponseSalt(session, envelope.salt_id)
  const { decryptEnvelopePayload } = await import('./encryptionEnvelope.ts')
  return decryptEnvelopePayload<T>(envelope, profile, session, responseSalt)
}

export async function encryptRequestPayload<T>(
  payload: T,
  profile: EncryptionProfile,
  session: EncryptionSession,
): Promise<EncryptedApiResponse> {
  const requestSalt = await takeSaltLease(session, 'request', profile)
  const { encryptEnvelopePayload } = await import('./encryptionEnvelope.ts')
  return encryptEnvelopePayload(payload, profile, session, requestSalt)
}

export async function createEncryptionRequestHeaders(
  session: EncryptionSession,
  profile: EncryptionProfile,
): Promise<Record<string, string>> {
  const [esidSalt, responseSalt] = await takeSaltLeases(session, [
    { purpose: 'esid', profile: null },
    { purpose: 'response', profile },
  ])
  await ensureEncryptionSidCookie(session)
  rememberResponseSalt(session, responseSalt)
  return {
    'X-Encryption-Session': session.id,
    'X-Encryption-Esid-Salt': esidSalt.leaseId,
    'X-Encryption-Response-Salt': responseSalt.leaseId,
  }
}

export async function takeLoginCapsuleSalt(
  session: EncryptionSession,
): Promise<EncryptionSaltLease> {
  return takeSaltLease(session, 'login_capsule', 'sensitive-v1')
}

function rememberResponseSalt(
  session: EncryptionSession,
  lease: EncryptionSaltLease,
): void {
  responseSaltRegistry.set(responseSaltRegistryKey(session.id, lease.leaseId), lease)
}

async function createEncryptionSession(scope: EncryptionScope): Promise<EncryptionSession> {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveBits'],
  )
  const clientPublicJwk = await crypto.subtle.exportKey('jwk', keyPair.publicKey)
  if (!isBrowserPublicKey(clientPublicJwk)) {
    throw new Error('浏览器未能生成 P-256 公钥')
  }

  const response = await fetch(`${API_BASE_URL}/${scope}/encryption/sessions`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_public_key: {
        kty: 'EC',
        crv: 'P-256',
        x: clientPublicJwk.x,
        y: clientPublicJwk.y,
      },
    }),
  })

  if (!response.ok) {
    throw new Error('加密会话协商失败')
  }

  const sessionResponse = (await response.json()) as EncryptionSessionResponse
  if (sessionResponse.scope !== scope) {
    throw new Error('加密会话来源不匹配')
  }
  const serverPublicKey = await crypto.subtle.importKey(
    'jwk',
    {
      ...sessionResponse.server_public_key,
      ext: true,
    },
    { name: 'ECDH', namedCurve: 'P-256' },
    false,
    [],
  )
  const sharedBits = await crypto.subtle.deriveBits(
    { name: 'ECDH', public: serverPublicKey },
    keyPair.privateKey,
    256,
  )

  const session: EncryptionSession = {
    id: sessionResponse.session_id,
    scope: sessionResponse.scope,
    sharedSecret: sharedBits,
    profiles: sessionResponse.profiles,
    expiresAt: parseApiTime(sessionResponse.expires_at),
    loginChallenge: sessionResponse.login_challenge ?? null,
  }
  return session
}

async function ensureEncryptionSidCookie(session: EncryptionSession): Promise<void> {
  if (!session.esid) {
    const { createEncryptionSid } = await import('./encryptionEsid.ts')
    session.esid = await createEncryptionSid(session)
  }
  if (session.esidCookieWritten) {
    return
  }
  const maxAge = Math.max(0, Math.floor((session.expiresAt - Date.now()) / 1000))
  const secure = window.location.protocol === 'https:' ? 'Secure' : ''
  const cookiePath = esidCookiePath(session.scope)
  document.cookie = [
    `${ESID_COOKIE_NAME}=${encodeURIComponent(session.esid)}`,
    `Path=${cookiePath}`,
    `Max-Age=${maxAge}`,
    'SameSite=Lax',
    secure,
  ]
    .filter(Boolean)
    .join('; ')
  session.esidCookieWritten = true
}

async function takeSaltLease(
  session: EncryptionSession,
  purpose: SaltPurpose,
  profile: EncryptionProfile | null,
): Promise<EncryptionSaltLease> {
  if (Date.now() > session.expiresAt - 1_000) {
    throw new Error('加密会话已过期')
  }
  session.saltSocket ??= await getSaltSocket(session)
  const [lease] = await session.saltSocket.request(purpose, profile, 1)
  if (!lease) {
    throw new Error('salt lease missing')
  }
  if (
    lease.purpose !== purpose ||
    lease.scope !== session.scope ||
    lease.profile !== profile ||
    lease.expiresAt <= Date.now()
  ) {
    throw new Error('salt lease mismatch')
  }
  return lease
}

async function takeSaltLeases(
  session: EncryptionSession,
  requests: Array<{ purpose: SaltPurpose; profile: EncryptionProfile | null }>,
): Promise<EncryptionSaltLease[]> {
  if (Date.now() > session.expiresAt - 1_000) {
    throw new Error('加密会话已过期')
  }
  session.saltSocket ??= await getSaltSocket(session)
  const leases = await session.saltSocket.requestBatch(
    requests.map((request) => ({
      ...request,
      count: 1,
    })),
  )
  if (leases.length !== requests.length) {
    throw new Error('salt lease missing')
  }
  leases.forEach((lease, index) => {
    const request = requests[index]
    if (
      !request ||
      lease.purpose !== request.purpose ||
      lease.scope !== session.scope ||
      lease.profile !== request.profile ||
      lease.expiresAt <= Date.now()
    ) {
      throw new Error('salt lease mismatch')
    }
  })
  return leases
}

function consumeResponseSalt(
  session: EncryptionSession,
  saltId: string,
): EncryptionSaltLease {
  const salt = responseSaltRegistry.get(responseSaltRegistryKey(session.id, saltId))
  if (!salt) {
    throw new Error('响应 salt 不存在或已使用')
  }
  responseSaltRegistry.delete(responseSaltRegistryKey(session.id, saltId))
  return salt
}

async function createSaltSocket(
  session: EncryptionSession,
): Promise<NonNullable<EncryptionSession['saltSocket']>> {
  const { SaltLeaseSocket } = await import('./encryptionSaltSocket.ts')
  return new SaltLeaseSocket(session)
}

async function getSaltSocket(
  session: EncryptionSession,
): Promise<NonNullable<EncryptionSession['saltSocket']>> {
  if (session.saltSocket) {
    return session.saltSocket
  }
  session.saltSocketOpening ??= createSaltSocket(session)
    .then((socket) => {
      session.saltSocket = socket
      return socket
    })
    .finally(() => {
      session.saltSocketOpening = undefined
    })
  return session.saltSocketOpening
}

function responseSaltRegistryKey(sessionId: string, leaseId: string): string {
  return `${sessionId}:${leaseId}`
}

function esidCookiePath(scope: EncryptionScope): string {
  return `${apiCookieBasePath()}/${scope}`.replace(/\/{2,}/g, '/')
}

function apiCookieBasePath(): string {
  const pathname = new URL(API_BASE_URL, window.location.origin).pathname
  const normalized = pathname.replace(/\/+$/g, '')
  return normalized || '/'
}

function isBrowserPublicKey(value: JsonWebKey): value is BrowserPublicKey {
  return value.kty === 'EC' && value.crv === 'P-256' && !!value.x && !!value.y
}

function abortable<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) {
    return promise
  }
  if (signal.aborted) {
    return Promise.reject(abortError())
  }
  return new Promise<T>((resolve, reject) => {
    const abort = () => {
      reject(abortError())
    }
    signal.addEventListener('abort', abort, { once: true })
    promise.then(resolve, reject).finally(() => {
      signal.removeEventListener('abort', abort)
    })
  })
}

function abortError(): DOMException {
  return new DOMException('请求已取消', 'AbortError')
}
