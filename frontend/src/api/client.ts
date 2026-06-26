import { API_BASE_URL } from './config.ts'
import {
  createEncryptionRequestHeaders,
  decryptEncryptedResponse,
  encryptRequestPayload,
  getEncryptionSession,
} from './encryption.ts'

export const RATE_LIMIT_MESSAGE = '您的访问太频繁，请稍后重试'

import type {
  EncryptionScope,
  EncryptionProfile,
  EncryptionSession,
  EncryptedApiResponse,
} from './encryption.ts'

type ApiRequestOptions = {
  csrfToken?: string
  encryptRequest?: boolean
  encryptionScope?: EncryptionScope
  signal?: AbortSignal
  skipAuthRefresh?: boolean
}

type AuthRefreshHandler = () => Promise<boolean>
type RetryInitFactory = () => Promise<Pick<RequestInit, 'body' | 'headers'>>

let authRefreshHandler: AuthRefreshHandler | null = null

export function setAuthRefreshHandler(handler: AuthRefreshHandler | null): void {
  authRefreshHandler = handler
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function isRateLimitError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 429
}

export function publicErrorMessage(error: unknown, fallback: string): string {
  return isRateLimitError(error) ? RATE_LIMIT_MESSAGE : fallback
}

export async function apiGet<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return requestJson<T>(path, {
    headers: jsonHeaders(options),
    signal: options.signal,
    skipAuthRefresh: options.skipAuthRefresh,
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
    signal: options.signal,
    skipAuthRefresh: options.skipAuthRefresh,
  })
}

export async function apiGetEncrypted<T>(
  path: string,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<T> {
  try {
    const session = await getEncryptionSession(
      profile,
      options.encryptionScope ?? 'admin',
      options.signal,
    )
    const encryptionHeaders = await createEncryptionRequestHeaders(session, profile)
    return await requestJson<T>(path, {
      headers: jsonHeaders(options, { encryptionHeaders }),
      encryption: { profile, session },
      retryInit: async () => ({
        headers: jsonHeaders(options, {
          encryptionHeaders: await createEncryptionRequestHeaders(session, profile),
        }),
      }),
      signal: options.signal,
      skipAuthRefresh: options.skipAuthRefresh,
    })
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function apiPostEncrypted<TBody, TResponse>(
  path: string,
  body: TBody,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  try {
    const session = await getEncryptionSession(
      profile,
      options.encryptionScope ?? 'admin',
      options.signal,
    )
    const requestBody = options.encryptRequest
      ? await encryptRequestPayload(body, profile, session)
      : body
    const encryptionHeaders = await createEncryptionRequestHeaders(session, profile)
    const encryptedRetryInit: RetryInitFactory = async () => {
      const retryBody = options.encryptRequest
        ? await encryptRequestPayload(body, profile, session)
        : body
      return {
        headers: jsonHeaders(options, {
          includeContentType: true,
          encryptionHeaders: await createEncryptionRequestHeaders(session, profile),
        }),
        body: JSON.stringify(retryBody),
      }
    }
    return await requestJson<TResponse>(path, {
      method: 'POST',
      headers: jsonHeaders(options, {
        includeContentType: true,
        encryptionHeaders,
      }),
      body: JSON.stringify(requestBody),
      encryption: { profile, session },
      retryInit: encryptedRetryInit,
      signal: options.signal,
      skipAuthRefresh: options.skipAuthRefresh,
    })
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function apiPostFormEncrypted<TResponse>(
  path: string,
  body: FormData,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  try {
    const session = await getEncryptionSession(
      profile,
      options.encryptionScope ?? 'admin',
      options.signal,
    )
    const encryptionHeaders = await createEncryptionRequestHeaders(session, profile)
    return await requestJson<TResponse>(path, {
      method: 'POST',
      headers: jsonHeaders(options, {
        encryptionHeaders,
      }),
      body,
      encryption: { profile, session },
      retryInit: async () => ({
        headers: jsonHeaders(options, {
          encryptionHeaders: await createEncryptionRequestHeaders(session, profile),
        }),
        body,
      }),
      signal: options.signal,
      skipAuthRefresh: options.skipAuthRefresh,
    })
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function apiPatchEncrypted<TBody, TResponse>(
  path: string,
  body: TBody,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  try {
    const session = await getEncryptionSession(
      profile,
      options.encryptionScope ?? 'admin',
      options.signal,
    )
    const requestBody = options.encryptRequest
      ? await encryptRequestPayload(body, profile, session)
      : body
    const encryptionHeaders = await createEncryptionRequestHeaders(session, profile)
    const encryptedRetryInit: RetryInitFactory = async () => {
      const retryBody = options.encryptRequest
        ? await encryptRequestPayload(body, profile, session)
        : body
      return {
        headers: jsonHeaders(options, {
          includeContentType: true,
          encryptionHeaders: await createEncryptionRequestHeaders(session, profile),
        }),
        body: JSON.stringify(retryBody),
      }
    }
    return await requestJson<TResponse>(path, {
      method: 'PATCH',
      headers: jsonHeaders(options, {
        includeContentType: true,
        encryptionHeaders,
      }),
      body: JSON.stringify(requestBody),
      encryption: { profile, session },
      retryInit: encryptedRetryInit,
      signal: options.signal,
      skipAuthRefresh: options.skipAuthRefresh,
    })
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export async function apiDeleteEncrypted<TResponse>(
  path: string,
  profile: EncryptionProfile,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  try {
    const session = await getEncryptionSession(
      profile,
      options.encryptionScope ?? 'admin',
      options.signal,
    )
    const encryptionHeaders = await createEncryptionRequestHeaders(session, profile)
    return await requestJson<TResponse>(path, {
      method: 'DELETE',
      headers: jsonHeaders(options, {
        encryptionHeaders,
      }),
      encryption: { profile, session },
      retryInit: async () => ({
        headers: jsonHeaders(options, {
          encryptionHeaders: await createEncryptionRequestHeaders(session, profile),
        }),
      }),
      signal: options.signal,
      skipAuthRefresh: options.skipAuthRefresh,
    })
  } catch (error) {
    throw normalizeApiError(error)
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit & {
    encryption?: { profile: EncryptionProfile; session: EncryptionSession }
    retryInit?: RetryInitFactory
    skipAuthRefresh?: boolean
  },
): Promise<T> {
  const { encryption, retryInit, skipAuthRefresh, ...fetchInit } = init
  let response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...fetchInit,
  })

  if (response.status === 401 && !skipAuthRefresh && authRefreshHandler) {
    const refreshed = await authRefreshHandler()
    if (refreshed) {
      if (retryInit) {
        Object.assign(fetchInit, await retryInit())
      }
      response = await fetch(`${API_BASE_URL}${path}`, {
        credentials: 'include',
        ...fetchInit,
      })
    }
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
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

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.clone().json()) as {
      detail?: unknown
    }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
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
    }
  } catch {
    return response.statusText
  }
  return response.statusText
}

function jsonHeaders(
  options: ApiRequestOptions,
  config: {
    includeContentType?: boolean
    encryptionHeaders?: Record<string, string>
  } = {},
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

  if (config.encryptionHeaders) {
    Object.assign(headers, config.encryptionHeaders)
  }

  return headers
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

function normalizeApiError(error: unknown): unknown {
  if (error instanceof ApiError) {
    return error
  }
  if (isSaltPolicyError(error)) {
    return new ApiError(RATE_LIMIT_MESSAGE, 429)
  }
  return error
}

function isSaltPolicyError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false
  }
  return (
    error.name === 'EncryptionSessionRateLimitError' ||
    error.name === 'SaltSocketPolicyError' ||
    error.message.includes('encryption session rate limited') ||
    error.message.includes('salt lease socket closed by policy') ||
    error.message.includes('salt lease socket temporarily blocked by policy')
  )
}
