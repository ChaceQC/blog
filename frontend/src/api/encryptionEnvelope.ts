import {
  base64urlDecode,
  base64urlEncode,
  decoder,
  encoder,
  textBytes,
} from './encryptionCore.ts'

import type {
  EncryptedApiResponse,
  EncryptionProfile,
  EncryptionSaltLease,
  EncryptionSession,
} from './encryptionTypes.ts'

export async function decryptEnvelopePayload<T>(
  envelope: EncryptedApiResponse,
  profile: EncryptionProfile,
  session: EncryptionSession,
  responseSalt: EncryptionSaltLease,
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

export async function encryptEnvelopePayload<T>(
  payload: T,
  profile: EncryptionProfile,
  session: EncryptionSession,
  requestSalt: EncryptionSaltLease,
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
