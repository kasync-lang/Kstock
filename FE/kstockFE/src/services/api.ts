/**
 * Base API client.
 *
 * Two back-end services are exposed:
 *   - AUTH_BASE_URL  → AuthenApp  (Python / FastAPI, default :8000, prefix /api/v1)
 *   - API_BASE_URL   → InteractionApp (Go / Gin,      default :8080, prefix /api)
 *
 * Override via Vite environment variables:
 *   VITE_AUTH_BASE_URL
 *   VITE_API_BASE_URL
 */

export const AUTH_BASE_URL =
  import.meta.env.VITE_AUTH_BASE_URL ?? 'http://localhost:8000/api/v1'


console.log(import.meta.env.VITE_AUTH_BASE_URL)
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080/api'

// ─── Token storage ───────────────────────────────────────────────────────────

const TOKEN_KEY = 'kstock_access_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// ─── Fetch wrappers ───────────────────────────────────────────────────────────

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions {
  /** Whether to attach the Bearer token (default: true). */
  auth?: boolean
  /** Request body (will be JSON-serialised). */
  body?: unknown
  /** Extra query-string parameters. */
  params?: Record<string, string | number | boolean | undefined>
}

function buildUrl(
  base: string,
  path: string,
  params?: RequestOptions['params'],
): string {
  const url = new URL(`${base}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) url.searchParams.set(k, String(v))
    })
  }
  return url.toString()
}

async function request<T>(
  baseUrl: string,
  method: HttpMethod,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { auth = true, body, params } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(buildUrl(baseUrl, path, params), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const err = await res.json()
      message = err?.detail ?? err?.error ?? message
    } catch {
      /* ignore parse error */
    }
    throw new Error(message)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}

// ─── Convenience factories ────────────────────────────────────────────────────

/** Call the AuthenApp service (Python / FastAPI). */
export function authRequest<T>(
  method: HttpMethod,
  path: string,
  options?: RequestOptions,
): Promise<T> {
  return request<T>(AUTH_BASE_URL, method, path, options)
}

/** Call the InteractionApp service (Go / Gin) with Bearer token. */
export function apiRequest<T>(
  method: HttpMethod,
  path: string,
  options?: RequestOptions,
): Promise<T> {
  return request<T>(API_BASE_URL, method, path, options)
}

/**
 * Build a multipart/form-data fetch call (used for OAuth2 password flow).
 * The `Content-Type` header is intentionally omitted so the browser sets the
 * correct boundary automatically.
 */
export async function formRequest<T>(
  baseUrl: string,
  path: string,
  fields: Record<string, string>,
): Promise<T> {
  const body = new URLSearchParams(fields)
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const err = await res.json()
      message = err?.detail ?? err?.error ?? message
    } catch {
      /* ignore */
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}
