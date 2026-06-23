import {
  base64urlEncode,
  concatBytes,
  encoder,
  toArrayBuffer,
  uint32be,
} from './encryptionCore.ts'
import { ContextOpcode, binaryContext } from './encryptionContext.ts'
import { loadEsidWasmByteMixer } from './encryptionWasm.ts'

import type { EncryptionSession } from './encryptionTypes.ts'

const ESID_VERSION = 1
const ESID_NONCE_LENGTH = 16
const ESID_TAG_LENGTH = 16
const ESID_ROUNDS = 8
const ESID_PURPOSE_ID = 1
const ESID_STREAM_LABELS = {
  mask: 1,
  rotate: 2,
  perm: 3,
} as const

export async function createEncryptionSid(
  session: EncryptionSession,
): Promise<string> {
  const key = await deriveEsidKey(session, ['sign', 'verify'])
  const nonce = crypto.getRandomValues(new Uint8Array(ESID_NONCE_LENGTH))
  const payload = JSON.stringify({
    exp: Math.floor(session.expiresAt / 1000),
    iat: Math.floor(Date.now() / 1000),
    purpose: ESID_PURPOSE_ID,
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
  session: EncryptionSession,
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
      salt: await binaryContext({
        seed: session.contextSeed,
        opcode: ContextOpcode.EsidKey,
        scope: session.scope,
        purpose: 'esid',
        sessionId: session.id,
        labelId: 1,
      }),
      info: await binaryContext({
        seed: session.contextSeed,
        opcode: ContextOpcode.EsidKey,
        scope: session.scope,
        purpose: 'esid',
        sessionId: session.id,
        labelId: 2,
      }),
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

async function transformEsidForward(
  data: Uint8Array,
  key: CryptoKey,
  nonce: Uint8Array,
): Promise<Uint8Array> {
  let value = new Uint8Array(data)
  const byteMix = await loadEsidWasmByteMixer()
  for (let roundIndex = 0; roundIndex < ESID_ROUNDS; roundIndex += 1) {
    const permutation = await esidPermutation(value.length, key, nonce, roundIndex)
    value = Uint8Array.from(permutation, (index) => value[index] ?? 0)
    const mask = await esidStream(key, nonce, 'mask', roundIndex, value.length)
    const shifts = await esidStream(key, nonce, 'rotate', roundIndex, value.length)
    for (let index = 0; index < value.length; index += 1) {
      value[index] = byteMix(
        value[index] ?? 0,
        mask[index] ?? 0,
        shifts[index] ?? 0,
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
            new Uint8Array([
              ContextOpcode.EsidStream,
              ESID_STREAM_LABELS[label],
              roundIndex,
            ]),
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
