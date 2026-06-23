import { API_BASE_URL } from './config.ts'
import {
  base64urlDecode,
  base64urlEncode,
  decoder,
  encoder,
  sleep,
  toArrayBuffer,
  toError,
} from './encryptionCore.ts'
import { ContextOpcode, binaryContext } from './encryptionContext.ts'

import type {
  EncryptionProfile,
  EncryptionSaltLease,
  EncryptionScope,
  EncryptionSession,
  SaltLeaseRequestItem,
  SaltPurpose,
} from './encryptionTypes.ts'

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

type SaltBatchRequestPayload = {
  kind: 'salt_batch_request'
  items: Required<SaltLeaseRequestItem>[]
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

const SALT_SOCKET_OPEN_TIMEOUT_MS = 8_000
const SALT_SOCKET_REQUEST_TIMEOUT_MS = 8_000
const SALT_SOCKET_HEARTBEAT_INTERVAL_MS = 25_000
const SALT_SOCKET_MAX_MISSED_PONGS = 2
const SALT_SOCKET_RECONNECT_BASE_MS = 1_000
const SALT_SOCKET_RECONNECT_MAX_MS = 30_000

export class SaltLeaseSocket {
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
    return this.requestBatch([{ purpose, profile, count }])
  }

  async requestBatch(
    items: SaltLeaseRequestItem[],
  ): Promise<EncryptionSaltLease[]> {
    const task = this.queue
      .catch(() => undefined)
      .then(() => this.performRequest(normalizeRequestItems(items)))
    this.queue = task.then(
      () => undefined,
      () => undefined,
    )
    return task
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

  private async performRequest(
    items: Required<SaltLeaseRequestItem>[],
  ): Promise<EncryptionSaltLease[]> {
    let lastError: Error | null = null
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        return await this.sendSaltRequest(items)
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
    items: Required<SaltLeaseRequestItem>[],
  ): Promise<EncryptionSaltLease[]> {
    if (this.pending) {
      throw new Error('salt lease request is already pending')
    }
    const socket = await this.ensureSocket()
    const frame = await this.wrapPayload(
      items.length === 1
        ? {
            kind: 'salt_request',
            purpose: items[0]?.purpose ?? 'esid',
            profile: items[0]?.profile ?? null,
            count: items[0]?.count ?? 1,
          }
        : {
            kind: 'salt_batch_request',
            items,
          },
    )
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
      const timeoutId = window.setTimeout(() => {
        if (settled) {
          return
        }
        settled = true
        cleanup()
        this.closeSocketForReconnect(new Error('salt lease socket open timed out'))
        reject(new Error('salt lease socket open timed out'))
      }, SALT_SOCKET_OPEN_TIMEOUT_MS)
      const cleanup = () => {
        window.clearTimeout(timeoutId)
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
      let settled = false
      const timeoutId = window.setTimeout(() => {
        if (settled) {
          return
        }
        settled = true
        cleanup()
        reject(new Error('salt lease socket open timed out'))
      }, SALT_SOCKET_OPEN_TIMEOUT_MS)
      const cleanup = () => {
        window.clearTimeout(timeoutId)
        socket.removeEventListener('open', handleOpen)
        socket.removeEventListener('error', handleError)
        socket.removeEventListener('close', handleClose)
      }
      const handleOpen = () => {
        if (settled) {
          return
        }
        settled = true
        cleanup()
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

  private async wrapPayload(
    payload: SaltRequestPayload | SaltBatchRequestPayload | SaltPingPayload,
  ): Promise<SaltFrame> {
    const wrapSalt = crypto.getRandomValues(new Uint8Array(32))
    const nonce = crypto.getRandomValues(new Uint8Array(12))
    const key = await deriveSaltWrapKey(this.session, wrapSalt, ['encrypt'])
    const ciphertext = await crypto.subtle.encrypt(
      {
        name: 'AES-GCM',
        iv: nonce,
        additionalData: await saltWrapAssociatedData(this.session),
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
      this.session,
      new Uint8Array(base64urlDecode(frame.wrap_salt)),
      ['decrypt'],
    )
    const plaintext = await crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: base64urlDecode(frame.nonce),
        additionalData: await saltWrapAssociatedData(this.session),
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

function normalizeRequestItems(
  items: SaltLeaseRequestItem[],
): Required<SaltLeaseRequestItem>[] {
  if (items.length < 1 || items.length > 8) {
    throw new Error('invalid salt lease request count')
  }
  const totalCount = items.reduce((total, item) => total + (item.count ?? 1), 0)
  if (totalCount < 1 || totalCount > 8) {
    throw new Error('invalid salt lease request count')
  }
  return items.map((item) => ({
    purpose: item.purpose,
    profile: item.profile ?? null,
    count: item.count ?? 1,
  }))
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

async function deriveSaltWrapKey(
  session: EncryptionSession,
  wrapSalt: Uint8Array,
  usages: KeyUsage[],
): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    session.sharedSecret,
    'HKDF',
    false,
    ['deriveKey'],
  )
  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: toArrayBuffer(wrapSalt),
      info: await binaryContext({
        seed: session.contextSeed,
        opcode: ContextOpcode.WssWrapKey,
        scope: session.scope,
        sessionId: session.id,
      }),
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    usages,
  )
}

async function saltWrapAssociatedData(
  session: EncryptionSession,
): Promise<ArrayBuffer> {
  return binaryContext({
    seed: session.contextSeed,
    opcode: ContextOpcode.WssWrapAad,
    scope: session.scope,
    sessionId: session.id,
  })
}

function saltWebSocketUrl(scope: EncryptionScope): string {
  const baseUrl = new URL(API_BASE_URL, window.location.origin)
  const pathname = `${baseUrl.pathname.replace(/\/+$/g, '')}/${scope}/encryption/salts`
  baseUrl.pathname = pathname.replace(/\/{2,}/g, '/')
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  return baseUrl.toString()
}
