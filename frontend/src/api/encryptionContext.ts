import {
  concatBytes,
  encoder,
  toArrayBuffer,
  uint32be,
} from './encryptionCore.ts'

import type {
  EncryptionProfile,
  EncryptionScope,
  SaltPurpose,
} from './encryptionTypes.ts'

export const ContextOpcode = {
  JsonKey: 1,
  JsonAad: 2,
  WssWrapKey: 3,
  WssWrapAad: 4,
  EsidKey: 5,
  EsidStream: 6,
  LoginEnc: 7,
  LoginMac: 8,
} as const

export type ContextOpcode = (typeof ContextOpcode)[keyof typeof ContextOpcode]

type BinaryContextInput = {
  seed: ArrayBuffer
  opcode: ContextOpcode
  scope: EncryptionScope
  profile?: EncryptionProfile | null
  purpose?: SaltPurpose | null
  sessionId: string
  leaseId?: string | null
  challengeId?: string | null
  labelId?: number
  roundIndex?: number
  counter?: number
}

const CONTEXT_SEED_BYTES = 32
const CONTEXT_VERSION = 3

export async function binaryContext({
  seed,
  opcode,
  scope,
  profile = null,
  purpose = null,
  sessionId,
  leaseId = null,
  challengeId = null,
  labelId = 0,
  roundIndex = 0,
  counter = 0,
}: BinaryContextInput): Promise<ArrayBuffer> {
  const seedBytes = new Uint8Array(seed)
  if (seedBytes.byteLength !== CONTEXT_SEED_BYTES) {
    throw new Error('invalid encryption context seed')
  }
  return toArrayBuffer(
    concatBytes(
      seedBytes,
      new Uint8Array([
        CONTEXT_VERSION,
        opcode,
        scopeId(scope),
        profileId(profile),
        purposeId(purpose),
        labelId & 0xff,
        roundIndex & 0xff,
      ]),
      uint32be(counter),
      await digestText(sessionId),
      await digestText(leaseId),
      await digestText(challengeId),
    ),
  )
}

export function scopeId(scope: EncryptionScope): number {
  if (scope === 'admin') {
    return 1
  }
  if (scope === 'public') {
    return 2
  }
  throw new Error('invalid encryption scope')
}

export function profileId(profile: EncryptionProfile | null): number {
  if (profile === null) {
    return 0
  }
  if (profile === 'sensitive-v1') {
    return 1
  }
  if (profile === 'content-v1') {
    return 2
  }
  throw new Error('invalid encryption profile')
}

export function purposeId(purpose: SaltPurpose | null): number {
  if (purpose === null) {
    return 0
  }
  if (purpose === 'esid') {
    return 1
  }
  if (purpose === 'login_capsule') {
    return 2
  }
  if (purpose === 'request') {
    return 3
  }
  if (purpose === 'response') {
    return 4
  }
  throw new Error('invalid salt purpose')
}

async function digestText(value: string | null): Promise<Uint8Array> {
  if (value === null) {
    return new Uint8Array(32)
  }
  return new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(value)))
}
