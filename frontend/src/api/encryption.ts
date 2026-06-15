import { API_BASE_URL } from './config.ts'

export type EncryptionProfile = 'sensitive-v1' | 'content-v1'

export type EncryptedApiResponse = {
  encrypted: true
  session_id: string
  profile: EncryptionProfile
  algorithm: 'AES-256-GCM-HKDF-SHA256'
  nonce: string
  ciphertext: string
}

type BrowserPublicKey = {
  kty: 'EC'
  crv: 'P-256'
  x: string
  y: string
}

type EncryptionSessionResponse = {
  session_id: string
  server_public_key: BrowserPublicKey
  profiles: EncryptionProfile[]
  expires_at: string
}

export type EncryptionSession = {
  id: string
  sharedSecret: ArrayBuffer
  profiles: EncryptionProfile[]
  expiresAt: number
}

let activeSession: EncryptionSession | undefined
let pendingSession: Promise<EncryptionSession> | undefined

const encoder = new TextEncoder()
const decoder = new TextDecoder()

export async function getEncryptionSession(
  profile: EncryptionProfile,
): Promise<EncryptionSession> {
  const now = Date.now()
  if (
    activeSession &&
    activeSession.expiresAt - now > 30_000 &&
    activeSession.profiles.includes(profile)
  ) {
    return activeSession
  }

  pendingSession ??= createEncryptionSession().finally(() => {
    pendingSession = undefined
  })
  activeSession = await pendingSession
  return activeSession
}

export async function decryptEncryptedResponse<T>(
  envelope: EncryptedApiResponse,
  profile: EncryptionProfile,
  session: EncryptionSession,
): Promise<T> {
  if (envelope.session_id !== session.id || envelope.profile !== profile) {
    throw new Error('加密响应会话不匹配')
  }

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
      salt: textBytes('blog-cms-encryption-v1'),
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
      salt: textBytes('blog-cms-encryption-v1'),
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
    encrypted: true,
    session_id: session.id,
    profile,
    algorithm: 'AES-256-GCM-HKDF-SHA256',
    nonce: base64urlEncode(nonce),
    ciphertext: base64urlEncode(new Uint8Array(ciphertext)),
  }
}

function isBrowserPublicKey(value: JsonWebKey): value is BrowserPublicKey {
  return value.kty === 'EC' && value.crv === 'P-256' && !!value.x && !!value.y
}

async function createEncryptionSession(): Promise<EncryptionSession> {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveBits'],
  )
  const clientPublicJwk = await crypto.subtle.exportKey('jwk', keyPair.publicKey)
  if (!isBrowserPublicKey(clientPublicJwk)) {
    throw new Error('浏览器未能生成 P-256 公钥')
  }

  const response = await fetch(`${API_BASE_URL}/admin/encryption/sessions`, {
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

  return {
    id: sessionResponse.session_id,
    sharedSecret: sharedBits,
    profiles: sessionResponse.profiles,
    expiresAt: Date.parse(sessionResponse.expires_at),
  }
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
