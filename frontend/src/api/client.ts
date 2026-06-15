import { API_BASE_URL } from './config.ts'
import {
  decryptEncryptedResponse,
  getEncryptionSession,
} from './encryption.ts'

import type {
  EncryptionProfile,
  EncryptionSession,
  EncryptedApiResponse,
} from './encryption.ts'

type ApiRequestOptions = {
  csrfToken?: string
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return requestJson<T>(path, {
    headers: jsonHeaders(options),
  })
}

export async function apiPost<TBody, TResponse>(
  path: string,
  body: TBody,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  return requestJson<TResponse>(path, {
    method: 'POST',
    headers: jsonHeaders(options, { includeContentType: true }),
    body: JSON.stringify(body),
  })
}

export async function apiGetEncrypted<T>(
  path: string,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<T> {
  const session = await getEncryptionSession(profile)
  return requestJson<T>(path, {
    headers: jsonHeaders(options, { encryptionSessionId: session.id }),
    encryption: { profile, session },
  })
}

export async function apiPostEncrypted<TBody, TResponse>(
  path: string,
  body: TBody,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  const session = await getEncryptionSession(profile)
  return requestJson<TResponse>(path, {
    method: 'POST',
    headers: jsonHeaders(options, {
      includeContentType: true,
      encryptionSessionId: session.id,
    }),
    body: JSON.stringify(body),
    encryption: { profile, session },
  })
}

export async function apiPatchEncrypted<TBody, TResponse>(
  path: string,
  body: TBody,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  const session = await getEncryptionSession(profile)
  return requestJson<TResponse>(path, {
    method: 'PATCH',
    headers: jsonHeaders(options, {
      includeContentType: true,
      encryptionSessionId: session.id,
    }),
    body: JSON.stringify(body),
    encryption: { profile, session },
  })
}

async function requestJson<T>(
  path: string,
  init: RequestInit & {
    encryption?: { profile: EncryptionProfile; session: EncryptionSession }
  },
): Promise<T> {
  const { encryption, ...fetchInit } = init
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...fetchInit,
  })

  if (!response.ok) {
    throw new ApiError(response.statusText, response.status)
  }

  const payload = (await response.json()) as T | EncryptedApiResponse
  if (encryption) {
    if (!isEncryptedApiResponse(payload)) {
      throw new Error('接口未返回加密响应')
    }
    return decryptEncryptedResponse<T>(payload, encryption.profile, encryption.session)
  }
  return payload as T
}

function jsonHeaders(
  options: ApiRequestOptions,
  config: { includeContentType?: boolean; encryptionSessionId?: string } = {},
): HeadersInit {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (config.includeContentType) {
    headers['Content-Type'] = 'application/json'
  }

  if (options.csrfToken) {
    headers['X-CSRF-Token'] = options.csrfToken
  }

  if (config.encryptionSessionId) {
    headers['X-Encryption-Session'] = config.encryptionSessionId
  }

  return headers
}

function isEncryptedApiResponse(value: unknown): value is EncryptedApiResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'encrypted' in value &&
    (value as { encrypted: unknown }).encrypted === true
  )
}
