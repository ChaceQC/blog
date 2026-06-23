import { API_BASE_URL } from './config.ts'
import { parseApiTime } from '../utils/datetime.ts'

export type EncryptionProfile = 'sensitive-v1' | 'content-v1'
export type EncryptionScope = 'admin' | 'public'

export type EncryptedApiResponse = {
  session_id: string
  profile: EncryptionProfile
  salt_id: string
  nonce: string
  ciphertext: string
}

export type EncryptionSaltLease = {
  leaseId: string
  purpose: SaltPurpose
  scope: EncryptionScope
  profile: EncryptionProfile | null
  salt: ArrayBuffer
  expiresAt: number
}

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

export type LoginChallenge = {
  challenge_id: string
  challenge_salt: string
  expires_at: string
}

export type EncryptionSession = {
  id: string
  scope: EncryptionScope
  sharedSecret: ArrayBuffer
  profiles: EncryptionProfile[]
  expiresAt: number
  loginChallenge?: LoginChallenge | null
  saltSocket?: SaltLeaseSocket
}

const ESID_COOKIE_NAME = 'esid'
const ESID_VERSION = 1
const ESID_NONCE_LENGTH = 16
const ESID_TAG_LENGTH = 16
const ESID_ROUNDS = 8
const SALT_WRAP_INFO = 'blog-cms:wss-salt-wrap:v1'
const SALT_SOCKET_REQUEST_TIMEOUT_MS = 8_000
const SALT_SOCKET_HEARTBEAT_INTERVAL_MS = 25_000
const SALT_SOCKET_MAX_MISSED_PONGS = 2
const SALT_SOCKET_RECONNECT_BASE_MS = 1_000
const SALT_SOCKET_RECONNECT_MAX_MS = 30_000

const activeSessions = new Map<EncryptionScope, EncryptionSession>()
const pendingSessions = new Map<EncryptionScope, Promise<EncryptionSession>>()

const encoder = new TextEncoder()
const decoder = new TextDecoder()
type SaltPurpose = 'esid' | 'login_capsule' | 'request' | 'response'

type SaltFrame = {
  session_id: string
  wrap_salt: string
  nonce: string
  ciphertext: string
}

type SaltLeaseWire = {
  lease_id: string
  purpose: SaltPurpose
  scope: EncryptionScope
  profile: EncryptionProfile | null
  salt: string
  expires_at: number
}

type SaltLeaseResponse = {
  type: 'salt_leases'
  frames: SaltFrame[]
}

type SaltPongResponse = {
  type: 'pong'
  frame: SaltFrame
}

type SaltSocketResponse = SaltLeaseResponse | SaltPongResponse

type SaltRequestPayload = {
  kind: 'salt_request'
  purpose: SaltPurpose
  profile: EncryptionProfile | null
  count: number
}

type SaltPingPayload = {
  kind: 'ping'
  seq: number
  ts: number
}

type SaltPongWire = {
  kind: 'pong'
  seq: number
  ts: number
}

class SaltLeaseSocket {
  private readonly session: EncryptionSession
  private socket: WebSocket | null = null
  private opening: Promise<WebSocket> | null = null
  private queue: Promise<void> = Promise.resolve()
  private pending:
    | {
        resolve: (leases: EncryptionSaltLease[]) => void
        reject: (error: Error) => void
        timeoutId: number
      }
    | null = null
  private heartbeatId: number | null = null
  private reconnectId: number | null = null
  private reconnectAttempts = 0
  private manualClose = false
  private pendingPongSeq: number | null = null
  private missedPongs = 0
  private heartbeatSeq = 0

  constructor(session: EncryptionSession) {
    this.session = session
  }

  async request(
    purpose: SaltPurpose,
    profile: EncryptionProfile | null = null,
    count = 1,
  ): Promise<EncryptionSaltLease[]> {
    const task = this.queue
      .catch(() => undefined)
      .then(() => this.performRequest(purpose, profile, count))
    this.queue = task.then(
      () => undefined,
      () => undefined,
    )
    return task
  }

  private async performRequest(
    purpose: SaltPurpose,
    profile: EncryptionProfile | null,
    count: number,
  ): Promise<EncryptionSaltLease[]> {
    let lastError: Error | null = null
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        return await this.sendSaltRequest(purpose, profile, count)
      } catch (error) {
        const normalizedError = toError(error, 'salt lease request failed')
        if (!isRetryableSaltSocketError(normalizedError) || attempt > 0) {
          throw normalizedError
        }
        lastError = normalizedError
        this.closeSocketForReconnect(normalizedError)
        await sleep(this.nextReconnectDelay())
      }
    }
    throw lastError ?? new Error('salt lease request failed')
  }

  private async sendSaltRequest(
    purpose: SaltPurpose,
    profile: EncryptionProfile | null,
    count: number,
  ): Promise<EncryptionSaltLease[]> {
    if (this.pending) {
      throw new Error('salt lease request is already pending')
    }
    const socket = await this.ensureSocket()
    const frame = await this.wrapPayload({
      kind: 'salt_request',
      purpose,
      profile,
      count,
    })
    return new Promise<EncryptionSaltLease[]>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        this.pending = null
        reject(new Error('salt lease request timed out'))
      }, SALT_SOCKET_REQUEST_TIMEOUT_MS)
      this.pending = { resolve, reject, timeoutId }
      try {
        socket.send(JSON.stringify(frame))
      } catch (error) {
        window.clearTimeout(timeoutId)
        this.pending = null
        reject(toError(error, 'salt lease socket send failed'))
      }
    })
  }

  close(): void {
    this.manualClose = true
    this.clearHeartbeat()
    this.clearReconnectTimer()
    this.rejectPending(new Error('salt lease socket closed'))
    this.socket?.close()
    this.socket = null
    this.opening = null
  }

  private ensureSocket(): Promise<WebSocket> {
    this.manualClose = false
    this.clearReconnectTimer()
    if (Date.now() > this.session.expiresAt - 1_000) {
      return Promise.reject(new Error('加密会话已过期'))
    }
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      if (this.socket.readyState === WebSocket.OPEN) {
        return Promise.resolve(this.socket)
      }
      return this.opening ?? this.waitForSocketOpen(this.socket)
    }

    return this.openSocket()
  }

  private openSocket(): Promise<WebSocket> {
    const socket = new WebSocket(saltWebSocketUrl(this.session.scope))
    this.socket = socket
    socket.addEventListener('message', (event) => {
      void this.handleMessage(event)
    })
    socket.addEventListener('close', () => {
      this.handleSocketClosed(socket, new Error('salt lease socket closed'))
    })
    socket.addEventListener('error', () => {
      this.closeSocketForReconnect(new Error('salt lease socket failed'))
    })

    this.opening = new Promise<WebSocket>((resolve, reject) => {
      let settled = false
      const cleanup = () => {
        socket.removeEventListener('open', handleOpen)
        socket.removeEventListener('error', handleError)
        socket.removeEventListener('close', handleClose)
      }
      const handleOpen = () => {
        settled = true
        cleanup()
        this.opening = null
        this.reconnectAttempts = 0
        this.startHeartbeat()
        resolve(socket)
      }
      const handleError = () => {
        if (settled) {
          return
        }
        settled = true
        cleanup()
        reject(new Error('salt lease socket failed'))
      }
      const handleClose = () => {
        if (settled) {
          return
        }
        settled = true
        cleanup()
        reject(new Error('salt lease socket closed'))
      }
      socket.addEventListener('open', handleOpen, { once: true })
      socket.addEventListener('error', handleError, { once: true })
      socket.addEventListener('close', handleClose, { once: true })
    })
    return this.opening
  }

  private async handleMessage(event: MessageEvent): Promise<void> {
    try {
      const response = JSON.parse(String(event.data)) as SaltSocketResponse
      if (response.type === 'pong') {
        await this.handlePong(response.frame)
        return
      }
      const pending = this.pending
      if (!pending) {
        return
      }
      if (response.type !== 'salt_leases' || !Array.isArray(response.frames)) {
        throw new Error('invalid salt lease response')
      }
      const leases = await Promise.all(
        response.frames.map((frame) => this.unwrapLease(frame)),
      )
      window.clearTimeout(pending.timeoutId)
      this.pending = null
      pending.resolve(leases)
    } catch (error) {
      const pending = this.pending
      if (pending) {
        window.clearTimeout(pending.timeoutId)
        this.pending = null
        pending.reject(toError(error, 'invalid salt lease'))
        return
      }
      this.closeSocketForReconnect(toError(error, 'invalid salt lease socket frame'))
    }
  }

  private waitForSocketOpen(socket: WebSocket): Promise<WebSocket> {
    return new Promise<WebSocket>((resolve, reject) => {
      const cleanup = () => {
        socket.removeEventListener('open', handleOpen)
        socket.removeEventListener('error', handleError)
        socket.removeEventListener('close', handleClose)
      }
      const handleOpen = () => {
        cleanup()
        resolve(socket)
      }
      const handleError = () => {
        cleanup()
        reject(new Error('salt lease socket failed'))
      }
      const handleClose = () => {
        cleanup()
        reject(new Error('salt lease socket closed'))
      }
      socket.addEventListener('open', handleOpen, { once: true })
      socket.addEventListener('error', handleError, { once: true })
      socket.addEventListener('close', handleClose, { once: true })
    })
  }

  private startHeartbeat(): void {
    this.clearHeartbeat()
    this.pendingPongSeq = null
    this.missedPongs = 0
    this.heartbeatId = window.setInterval(() => {
      void this.sendHeartbeat()
    }, SALT_SOCKET_HEARTBEAT_INTERVAL_MS)
  }

  private clearHeartbeat(): void {
    if (this.heartbeatId !== null) {
      window.clearInterval(this.heartbeatId)
      this.heartbeatId = null
    }
    this.pendingPongSeq = null
    this.missedPongs = 0
  }

  private async sendHeartbeat(): Promise<void> {
    const socket = this.socket
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return
    }
    if (this.pendingPongSeq !== null) {
      this.missedPongs += 1
      if (this.missedPongs >= SALT_SOCKET_MAX_MISSED_PONGS) {
        this.closeSocketForReconnect(new Error('salt lease heartbeat timed out'))
        return
      }
    }
    this.heartbeatSeq = (this.heartbeatSeq % 2_147_483_647) + 1
    this.pendingPongSeq = this.heartbeatSeq
    try {
      const frame = await this.wrapPayload({
        kind: 'ping',
        seq: this.heartbeatSeq,
        ts: Math.floor(Date.now() / 1000),
      })
      if (this.socket === socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(frame))
      }
    } catch (error) {
      this.closeSocketForReconnect(toError(error, 'salt lease heartbeat failed'))
    }
  }

  private async handlePong(frame: SaltFrame): Promise<void> {
    const payload = await this.unwrapPayload(frame)
    if (!isSaltPongWire(payload)) {
      throw new Error('invalid salt lease pong')
    }
    if (payload.seq === this.pendingPongSeq) {
      this.pendingPongSeq = null
      this.missedPongs = 0
    }
  }

  private handleSocketClosed(socket: WebSocket, error: Error): void {
    if (this.socket !== socket) {
      return
    }
    this.socket = null
    this.opening = null
    this.clearHeartbeat()
    this.rejectPending(error)
    this.scheduleReconnect()
  }

  private closeSocketForReconnect(error: Error): void {
    const socket = this.socket
    if (!socket) {
      this.scheduleReconnect()
      return
    }
    this.handleSocketClosed(socket, error)
    if (socket.readyState !== WebSocket.CLOSED && socket.readyState !== WebSocket.CLOSING) {
      socket.close()
    }
  }

  private rejectPending(error: Error): void {
    if (!this.pending) {
      return
    }
    window.clearTimeout(this.pending.timeoutId)
    this.pending.reject(error)
    this.pending = null
  }

  private scheduleReconnect(): void {
    if (
      this.manualClose ||
      this.reconnectId !== null ||
      Date.now() > this.session.expiresAt - 1_000
    ) {
      return
    }
    const delay = this.nextReconnectDelay()
    this.reconnectId = window.setTimeout(() => {
      this.reconnectId = null
      if (this.manualClose || Date.now() > this.session.expiresAt - 1_000) {
        return
      }
      void this.openSocket().catch(() => undefined)
    }, delay)
  }

  private clearReconnectTimer(): void {
    if (this.reconnectId !== null) {
      window.clearTimeout(this.reconnectId)
      this.reconnectId = null
    }
  }

  private nextReconnectDelay(): number {
    const attempt = Math.min(this.reconnectAttempts, 5)
    this.reconnectAttempts += 1
    const baseDelay = Math.min(
      SALT_SOCKET_RECONNECT_MAX_MS,
      SALT_SOCKET_RECONNECT_BASE_MS * 2 ** attempt,
    )
    const jitter = Math.floor(Math.random() * Math.min(1_000, baseDelay / 4))
    return Math.min(SALT_SOCKET_RECONNECT_MAX_MS, baseDelay + jitter)
  }

  private async wrapPayload(payload: SaltRequestPayload | SaltPingPayload): Promise<SaltFrame> {
    const wrapSalt = crypto.getRandomValues(new Uint8Array(32))
    const nonce = crypto.getRandomValues(new Uint8Array(12))
    const key = await deriveSaltWrapKey(this.session.sharedSecret, wrapSalt, [
      'encrypt',
    ])
    const ciphertext = await crypto.subtle.encrypt(
      {
        name: 'AES-GCM',
        iv: nonce,
        additionalData: saltWrapAssociatedData(this.session.id),
        tagLength: 128,
      },
      key,
      encoder.encode(JSON.stringify(payload)),
    )
    return {
      session_id: this.session.id,
      wrap_salt: base64urlEncode(wrapSalt),
      nonce: base64urlEncode(nonce),
      ciphertext: base64urlEncode(new Uint8Array(ciphertext)),
    }
  }

  private async unwrapPayload(frame: SaltFrame): Promise<unknown> {
    if (frame.session_id !== this.session.id) {
      throw new Error('salt lease session mismatch')
    }
    const key = await deriveSaltWrapKey(
      this.session.sharedSecret,
      new Uint8Array(base64urlDecode(frame.wrap_salt)),
      ['decrypt'],
    )
    const plaintext = await crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: base64urlDecode(frame.nonce),
        additionalData: saltWrapAssociatedData(this.session.id),
        tagLength: 128,
      },
      key,
      base64urlDecode(frame.ciphertext),
    )
    return JSON.parse(decoder.decode(plaintext)) as unknown
  }

  private async unwrapLease(frame: SaltFrame): Promise<EncryptionSaltLease> {
    const lease = await this.unwrapPayload(frame)
    if (
      !isSaltLeaseWire(lease) ||
      lease.scope !== this.session.scope ||
      lease.expires_at * 1000 <= Date.now()
    ) {
      throw new Error('invalid salt lease')
    }
    return {
      leaseId: lease.lease_id,
      purpose: lease.purpose,
      scope: lease.scope,
      profile: lease.profile,
      salt: base64urlDecode(lease.salt),
      expiresAt: lease.expires_at * 1000,
    }
  }
}

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
    await refreshEncryptionSidCookie(activeSession)
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
  if (envelope.session_id !== session.id || envelope.profile !== profile) {
    throw new Error('加密响应会话不匹配')
  }
  const responseSalt = consumeResponseSalt(session, envelope.salt_id)

  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    session.sharedSecret,
    'HKDF',
    false,
    ['deriveKey'],
  )
  const aesKey = await crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: responseSalt.salt,
      info: textBytes(`blog-cms:${profile}`),
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt'],
  )
  const plaintext = await crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: base64urlDecode(envelope.nonce),
      additionalData: textBytes(`blog-cms:${profile}:json`),
      tagLength: 128,
    },
    aesKey,
    base64urlDecode(envelope.ciphertext),
  )

  return JSON.parse(decoder.decode(plaintext)) as T
}

export async function encryptRequestPayload<T>(
  payload: T,
  profile: EncryptionProfile,
  session: EncryptionSession,
): Promise<EncryptedApiResponse> {
  const requestSalt = await takeSaltLease(session, 'request', profile)
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    session.sharedSecret,
    'HKDF',
    false,
    ['deriveKey'],
  )
  const aesKey = await crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: requestSalt.salt,
      info: textBytes(`blog-cms:${profile}`),
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt'],
  )
  const nonce = crypto.getRandomValues(new Uint8Array(12))
  const ciphertext = await crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: nonce,
      additionalData: textBytes(`blog-cms:${profile}:json`),
      tagLength: 128,
    },
    aesKey,
    encoder.encode(JSON.stringify(payload)),
  )

  return {
    session_id: session.id,
    profile,
    salt_id: requestSalt.leaseId,
    nonce: base64urlEncode(nonce),
    ciphertext: base64urlEncode(new Uint8Array(ciphertext)),
  }
}

export async function createEncryptionRequestHeaders(
  session: EncryptionSession,
  profile: EncryptionProfile,
): Promise<Record<string, string>> {
  const esidSalt = await refreshEncryptionSidCookie(session)
  const responseSalt = await takeSaltLease(session, 'response', profile)
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

function isBrowserPublicKey(value: JsonWebKey): value is BrowserPublicKey {
  return value.kty === 'EC' && value.crv === 'P-256' && !!value.x && !!value.y
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
  session.saltSocket = new SaltLeaseSocket(session)
  await refreshEncryptionSidCookie(session)
  return session
}

async function refreshEncryptionSidCookie(
  session: EncryptionSession,
): Promise<EncryptionSaltLease> {
  const esidSalt = await takeSaltLease(session, 'esid', null)
  const esid = await createEncryptionSid(session, esidSalt.salt)
  const maxAge = Math.max(0, Math.floor((session.expiresAt - Date.now()) / 1000))
  const secure = window.location.protocol === 'https:' ? 'Secure' : ''
  const cookiePath = esidCookiePath(session.scope)
  document.cookie = [
    `${ESID_COOKIE_NAME}=${esid}`,
    `Path=${cookiePath}`,
    `Max-Age=${maxAge}`,
    'SameSite=Lax',
    secure,
  ]
    .filter(Boolean)
    .join('; ')
  return esidSalt
}

function esidCookiePath(scope: EncryptionScope): string {
  return `${apiCookieBasePath()}/${scope}`.replace(/\/{2,}/g, '/')
}

function apiCookieBasePath(): string {
  const pathname = new URL(API_BASE_URL, window.location.origin).pathname
  const normalized = pathname.replace(/\/+$/g, '')
  return normalized || '/'
}

async function createEncryptionSid(
  session: EncryptionSession,
  salt: ArrayBuffer,
): Promise<string> {
  const key = await deriveEsidKey(session.sharedSecret, session.scope, salt, [
    'sign',
    'verify',
  ])
  const nonce = crypto.getRandomValues(new Uint8Array(ESID_NONCE_LENGTH))
  const payload = JSON.stringify({
    exp: Math.floor(session.expiresAt / 1000),
    iat: Math.floor(Date.now() / 1000),
    purpose: 'encryption-session-binding',
    scope: session.scope,
    session_id: session.id,
  })
  const transformed = await transformEsidForward(encoder.encode(payload), key, nonce)
  const body = concatBytes(new Uint8Array([ESID_VERSION]), nonce, transformed)
  const tag = new Uint8Array(
    await crypto.subtle.sign('HMAC', key, toArrayBuffer(body)),
  ).slice(0, ESID_TAG_LENGTH)
  return base64urlEncode(concatBytes(body, tag))
}

async function deriveEsidKey(
  sharedSecret: ArrayBuffer,
  scope: EncryptionScope,
  salt: ArrayBuffer,
  usages: KeyUsage[],
): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    sharedSecret,
    'HKDF',
    false,
    ['deriveKey'],
  )
  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt,
      info: textBytes(`blog-cms:esid:${scope}`),
    },
    keyMaterial,
    {
      name: 'HMAC',
      hash: 'SHA-256',
      length: 256,
    },
    false,
    usages,
  )
}

async function takeSaltLease(
  session: EncryptionSession,
  purpose: SaltPurpose,
  profile: EncryptionProfile | null,
): Promise<EncryptionSaltLease> {
  if (Date.now() > session.expiresAt - 1_000) {
    throw new Error('加密会话已过期')
  }
  const socket = session.saltSocket ?? new SaltLeaseSocket(session)
  session.saltSocket = socket
  const [lease] = await socket.request(purpose, profile, 1)
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

const responseSaltRegistry = new Map<string, EncryptionSaltLease>()

export function rememberResponseSalt(
  session: EncryptionSession,
  lease: EncryptionSaltLease,
): void {
  responseSaltRegistry.set(responseSaltRegistryKey(session.id, lease.leaseId), lease)
}

function responseSaltRegistryKey(sessionId: string, leaseId: string): string {
  return `${sessionId}:${leaseId}`
}

function isSaltLeaseWire(value: unknown): value is SaltLeaseWire {
  if (!value || typeof value !== 'object') {
    return false
  }
  const lease = value as Partial<SaltLeaseWire>
  return (
    typeof lease.lease_id === 'string' &&
    isSaltPurpose(lease.purpose) &&
    isEncryptionScope(lease.scope) &&
    (lease.profile === null || isEncryptionProfile(lease.profile)) &&
    typeof lease.salt === 'string' &&
    typeof lease.expires_at === 'number'
  )
}

function isSaltPongWire(value: unknown): value is SaltPongWire {
  if (!value || typeof value !== 'object') {
    return false
  }
  const pong = value as Partial<SaltPongWire>
  return (
    pong.kind === 'pong' &&
    typeof pong.seq === 'number' &&
    Number.isInteger(pong.seq) &&
    typeof pong.ts === 'number' &&
    Number.isInteger(pong.ts)
  )
}

function isSaltPurpose(value: unknown): value is SaltPurpose {
  return (
    value === 'esid' ||
    value === 'login_capsule' ||
    value === 'request' ||
    value === 'response'
  )
}

function isEncryptionScope(value: unknown): value is EncryptionScope {
  return value === 'admin' || value === 'public'
}

function isEncryptionProfile(value: unknown): value is EncryptionProfile {
  return value === 'sensitive-v1' || value === 'content-v1'
}

function isRetryableSaltSocketError(error: Error): boolean {
  return (
    error.message.includes('socket') ||
    error.message.includes('timed out') ||
    error.message.includes('heartbeat')
  )
}

function toError(error: unknown, fallbackMessage: string): Error {
  return error instanceof Error ? error : new Error(fallbackMessage)
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds)
  })
}

async function deriveSaltWrapKey(
  sharedSecret: ArrayBuffer,
  wrapSalt: Uint8Array,
  usages: KeyUsage[],
): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    sharedSecret,
    'HKDF',
    false,
    ['deriveKey'],
  )
  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: toArrayBuffer(wrapSalt),
      info: textBytes(SALT_WRAP_INFO),
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    usages,
  )
}

function saltWrapAssociatedData(sessionId: string): ArrayBuffer {
  return textBytes(`blog-cms:wss-salt-wrap:${sessionId}`)
}

function saltWebSocketUrl(scope: EncryptionScope): string {
  const baseUrl = new URL(API_BASE_URL, window.location.origin)
  const pathname = `${baseUrl.pathname.replace(/\/+$/g, '')}/${scope}/encryption/salts`
  baseUrl.pathname = pathname.replace(/\/{2,}/g, '/')
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  return baseUrl.toString()
}

async function transformEsidForward(
  data: Uint8Array,
  key: CryptoKey,
  nonce: Uint8Array,
): Promise<Uint8Array> {
  let value = new Uint8Array(data)
  for (let roundIndex = 0; roundIndex < ESID_ROUNDS; roundIndex += 1) {
    const permutation = await esidPermutation(value.length, key, nonce, roundIndex)
    value = Uint8Array.from(permutation, (index) => value[index] ?? 0)
    const mask = await esidStream(key, nonce, 'mask', roundIndex, value.length)
    const shifts = await esidStream(key, nonce, 'rotate', roundIndex, value.length)
    for (let index = 0; index < value.length; index += 1) {
      value[index] = rotateLeft(
        ((value[index] ?? 0) ^ (mask[index] ?? 0)) & 0xff,
        (shifts[index] ?? 0) & 7,
      )
    }
  }
  return value
}

async function esidPermutation(
  length: number,
  key: CryptoKey,
  nonce: Uint8Array,
  roundIndex: number,
): Promise<number[]> {
  const indexes = Array.from({ length }, (_, index) => index)
  if (length <= 1) {
    return indexes
  }
  const stream = await esidStream(key, nonce, 'perm', roundIndex, (length - 1) * 4)
  let offset = 0
  for (let index = length - 1; index > 0; index -= 1) {
    const value =
      (((stream[offset] ?? 0) << 24) |
        ((stream[offset + 1] ?? 0) << 16) |
        ((stream[offset + 2] ?? 0) << 8) |
        (stream[offset + 3] ?? 0)) >>>
      0
    offset += 4
    const swapIndex = value % (index + 1)
    const current = indexes[index] ?? index
    indexes[index] = indexes[swapIndex] ?? swapIndex
    indexes[swapIndex] = current
  }
  return indexes
}

async function esidStream(
  key: CryptoKey,
  nonce: Uint8Array,
  label: 'mask' | 'perm' | 'rotate',
  roundIndex: number,
  length: number,
): Promise<Uint8Array> {
  const output = new Uint8Array(length)
  let written = 0
  let counter = 0
  while (written < length) {
    const chunk = new Uint8Array(
      await crypto.subtle.sign(
        'HMAC',
        key,
        toArrayBuffer(
          concatBytes(
            encoder.encode(`blog-cms-esid:${label}:`),
            new Uint8Array([roundIndex]),
            nonce,
            uint32be(counter),
          ),
        ),
      ),
    )
    output.set(chunk.slice(0, Math.min(chunk.length, length - written)), written)
    written += chunk.length
    counter += 1
  }
  return output
}

function rotateLeft(value: number, shift: number): number {
  if (shift === 0) {
    return value
  }
  return ((value << shift) | (value >>> (8 - shift))) & 0xff
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

function base64urlDecode(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = `${base64}${'='.repeat((4 - (base64.length % 4)) % 4)}`
  const binary = atob(padded)
  return toArrayBuffer(Uint8Array.from(binary, (char) => char.charCodeAt(0)))
}

function base64urlEncode(value: Uint8Array): string {
  const binary = Array.from(value, (byte) => String.fromCharCode(byte)).join('')
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function textBytes(value: string): ArrayBuffer {
  return toArrayBuffer(encoder.encode(value))
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(bytes.byteLength)
  new Uint8Array(buffer).set(bytes)
  return buffer
}

function concatBytes(...items: Uint8Array[]): Uint8Array {
  const totalLength = items.reduce((total, item) => total + item.byteLength, 0)
  const output = new Uint8Array(totalLength)
  let offset = 0
  for (const item of items) {
    output.set(item, offset)
    offset += item.byteLength
  }
  return output
}

function uint32be(value: number): Uint8Array {
  return new Uint8Array([
    (value >>> 24) & 0xff,
    (value >>> 16) & 0xff,
    (value >>> 8) & 0xff,
    value & 0xff,
  ])
}
