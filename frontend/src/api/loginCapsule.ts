import { ApiError } from './client.ts'
import { API_BASE_URL } from './config.ts'
import {
  createEncryptionRequestHeaders,
  createFreshEncryptionSession,
  decryptEncryptedResponse,
  takeLoginCapsuleSalt,
} from './encryption.ts'

import type {
  EncryptedApiResponse,
  EncryptionSaltLease,
  EncryptionSession,
} from './encryption.ts'

type LoginCapsuleRequest = {
  scheme: 'login-capsule-v2'
  session_id: string
  challenge_id: string
  salt_id: string
  nonce: string
  issued_at: number
  ciphertext: string
  tag: string
}

const LOGIN_CAPSULE_SCHEME = 'login-capsule-v2'
const LOGIN_CAPSULE_BUCKETS = [256, 512, 1024, 2048] as const

const encoder = new TextEncoder()

export async function apiPostLoginCapsule<TBody, TResponse>(
  path: string,
  body: TBody,
  signal?: AbortSignal,
): Promise<TResponse> {
  const session = await createFreshEncryptionSession('admin', signal)
  const capsule = await createLoginCapsule(path, body, session)
  const encryptionHeaders = await createEncryptionRequestHeaders(
    session,
    'sensitive-v1',
  )
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...encryptionHeaders,
    },
    body: JSON.stringify(capsule),
    signal,
  })

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }

  const payload = (await response.json()) as EncryptedApiResponse
  if (!isEncryptedApiResponse(payload)) {
    throw new Error('接口未返回加密响应')
  }
  return decryptEncryptedResponse<TResponse>(payload, 'sensitive-v1', session)
}

async function createLoginCapsule<TBody>(
  path: string,
  body: TBody,
  session: EncryptionSession,
): Promise<LoginCapsuleRequest> {
  const challenge = session.loginChallenge
  if (!challenge) {
    throw new Error('登录加密挑战缺失')
  }
  const loginSalt = await takeLoginCapsuleSalt(session)

  const plaintext = paddedPayload(body)
  const nonce = crypto.getRandomValues(new Uint8Array(16))
  const encryptionKey = await deriveLoginCapsuleKey(
    session,
    loginSalt,
    challenge.challenge_id,
    challenge.challenge_salt,
    'enc',
    'AES-CTR',
    ['encrypt'],
  )
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: 'AES-CTR', counter: nonce, length: 128 },
      encryptionKey,
      toArrayBuffer(plaintext),
    ),
  )

  const issuedAt = Math.floor(Date.now() / 1000)
  const capsuleWithoutTag: Omit<LoginCapsuleRequest, 'tag'> = {
    scheme: LOGIN_CAPSULE_SCHEME,
    session_id: session.id,
    challenge_id: challenge.challenge_id,
    salt_id: loginSalt.leaseId,
    nonce: base64urlEncode(nonce),
    issued_at: issuedAt,
    ciphertext: base64urlEncode(ciphertext),
  }
  const macKey = await deriveLoginCapsuleKey(
    session,
    loginSalt,
    challenge.challenge_id,
    challenge.challenge_salt,
    'mac',
    'HMAC',
    ['sign'],
  )
  const tag = new Uint8Array(
    await crypto.subtle.sign(
      'HMAC',
      macKey,
      signingInput(path, capsuleWithoutTag),
    ),
  )

  return {
    ...capsuleWithoutTag,
    tag: base64urlEncode(tag),
  }
}

async function deriveLoginCapsuleKey(
  session: EncryptionSession,
  loginSalt: EncryptionSaltLease,
  challengeId: string,
  challengeSalt: string,
  purpose: 'enc' | 'mac',
  algorithm: 'AES-CTR' | 'HMAC',
  usages: KeyUsage[],
): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    session.sharedSecret,
    'HKDF',
    false,
    ['deriveKey'],
  )
  const derivedAlgorithm: AesKeyGenParams | HmacKeyGenParams =
    algorithm === 'AES-CTR'
      ? { name: 'AES-CTR', length: 256 }
      : { name: 'HMAC', hash: 'SHA-256', length: 256 }
  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: toArrayBuffer(
        concatBytes(
          new Uint8Array(loginSalt.salt),
          new Uint8Array(base64urlDecode(challengeSalt)),
        ),
      ),
      info: encoder.encode(
        `blog-login-v2:${purpose}:${session.id}:${challengeId}`,
      ),
    },
    keyMaterial,
    derivedAlgorithm,
    false,
    usages,
  )
}

function paddedPayload<TBody>(body: TBody): Uint8Array {
  const payload = encoder.encode(JSON.stringify(body))
  const bucket = LOGIN_CAPSULE_BUCKETS.find((size) => size >= payload.length + 2)
  if (!bucket) {
    throw new Error('登录请求体过大')
  }

  const padded = crypto.getRandomValues(new Uint8Array(bucket))
  padded[0] = (payload.length >>> 8) & 0xff
  padded[1] = payload.length & 0xff
  padded.set(payload, 2)
  return padded
}

function signingInput(
  path: string,
  capsule: Omit<LoginCapsuleRequest, 'tag'>,
): ArrayBuffer {
  const requestPath = new URL(`${API_BASE_URL}${path}`, window.location.origin)
    .pathname
  return toArrayBuffer(
    encoder.encode(
      [
        capsule.scheme,
        capsule.session_id,
        capsule.challenge_id,
        capsule.salt_id,
        'POST',
        requestPath,
        String(capsule.issued_at),
        capsule.nonce,
        capsule.ciphertext,
      ].join('\n'),
    ),
  )
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.clone().json()) as {
      detail?: unknown
    }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (Array.isArray(payload.detail)) {
      return (
        payload.detail
          .map((item) => {
            if (
              typeof item === 'object' &&
              item !== null &&
              'msg' in item &&
              typeof item.msg === 'string'
            ) {
              return item.msg
            }
            return null
          })
          .filter((item): item is string => item !== null)
          .join('；') || response.statusText
      )
    }
  } catch {
    return response.statusText
  }
  return response.statusText
}

function isEncryptedApiResponse(value: unknown): value is EncryptedApiResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'session_id' in value &&
    'profile' in value &&
    'salt_id' in value &&
    'nonce' in value &&
    'ciphertext' in value
  )
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

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(bytes.byteLength)
  new Uint8Array(buffer).set(bytes)
  return buffer
}
