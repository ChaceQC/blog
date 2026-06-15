const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: jsonHeaders(options),
  })

  if (!response.ok) {
    throw new ApiError(response.statusText, response.status)
  }

  return response.json() as Promise<T>
}

export async function apiPost<TBody, TResponse>(
  path: string,
  body: TBody,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: jsonHeaders(options, { includeContentType: true }),
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new ApiError(response.statusText, response.status)
  }

  return response.json() as Promise<TResponse>
}

function jsonHeaders(
  options: ApiRequestOptions,
  config: { includeContentType?: boolean } = {},
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

  return headers
}
