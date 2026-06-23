export type EncryptionProfile = 'sensitive-v1' | 'content-v1'
export type EncryptionScope = 'admin' | 'public'
export type SaltPurpose = 'esid' | 'login_capsule' | 'request' | 'response'

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

export type SaltLeaseRequestItem = {
  purpose: SaltPurpose
  profile?: EncryptionProfile | null
  count?: number
}

export type LoginChallenge = {
  challenge_id: string
  challenge_salt: string
  expires_at: string
}

export type SaltSocketClient = {
  request: (
    purpose: SaltPurpose,
    profile?: EncryptionProfile | null,
    count?: number,
  ) => Promise<EncryptionSaltLease[]>
  requestBatch: (
    items: SaltLeaseRequestItem[],
  ) => Promise<EncryptionSaltLease[]>
  close: () => void
}

export type EncryptionSession = {
  id: string
  scope: EncryptionScope
  sharedSecret: ArrayBuffer
  profiles: EncryptionProfile[]
  expiresAt: number
  esid?: string
  esidCookieWritten?: boolean
  loginChallenge?: LoginChallenge | null
  saltSocket?: SaltSocketClient
  saltSocketOpening?: Promise<SaltSocketClient>
}
