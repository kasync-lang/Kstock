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
  import.meta.env.VITE_AUTH_BASE_URL ?? 'http://localhost:80/api/v1'

export const AUTH_ROOT_URL =
  import.meta.env.VITE_AUTH_ROOT_URL ?? AUTH_BASE_URL.replace(/\/api\/v1\/?$/, '')

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? '/api'

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

// ─── Session refresh (HttpOnly refresh-token cookie) ─────────────────────────

/** Path on AuthenApp used to exchange the refresh-token cookie for a new access token. */
const REFRESH_TOKEN_PATH = '/auth/refresh'

/** Query-string marker telling the login page the previous session has expired. */
export const SESSION_EXPIRED_REASON = 'session-expired'

/** Shape of the JSON error body returned by both back-end services. */
interface ApiErrorBody {
  code?: string
  message?: string
  detail?: string
  error?: string
}

function redirectToLoginForInvalidToken(): void {
  removeToken()
  if (window.location.pathname !== '/login') {
    window.location.replace(`/login?reason=${SESSION_EXPIRED_REASON}`)
  }
}

let refreshInFlight: Promise<string | null> | null = null

/**
 * POST /auth/refresh
 *
 * The refresh token lives in an HttpOnly cookie owned by AuthenApp, so it is
 * never read by JavaScript — `credentials: 'include'` is what forwards it. On
 * success the rotated cookie is set automatically and the freshly minted access
 * token is persisted to localStorage.
 *
 * Concurrent callers share a single in-flight request: the back-end rotates the
 * refresh token on every call, so firing two refreshes at once would trigger its
 * token-reuse detection and revoke the whole session.
 *
 * @returns the new access token, or `null` when the session is no longer valid.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

async function performRefresh(): Promise<string | null> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 8000)

  try {
    const res = await fetch(`${AUTH_ROOT_URL}${REFRESH_TOKEN_PATH}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      signal: controller.signal,
    })

    if (!res.ok) return null

    const data = (await res.json()) as { access_token?: string; session_token?: string }
    const token = data.session_token || data.access_token
    if (!token) return null

    setToken(token)
    return token
  } catch {
    return null
  } finally {
    clearTimeout(timeoutId)
  }
}

// ─── Fetch wrappers ───────────────────────────────────────────────────────────

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  /** Whether to attach the Bearer token (default: true). */
  auth?: boolean
  /** Request body (will be JSON-serialised). */
  body?: unknown
  /** Extra query-string parameters. */
  params?: Record<string, string | number | boolean | undefined>
  /** Timeout in milliseconds (default: 5000ms for auth, 10000ms for general api). */
  timeoutMs?: number
  /**
   * Internal flag set when a request is replayed after a token refresh.
   * Guards against infinite retry loops. Do not set this manually.
   */
  isRetry?: boolean
}

function buildUrl(
  base: string,
  path: string,
  params?: RequestOptions['params'],
): string {
  const url = new URL(`${base}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) url.searchParams.set(k, String(v))
    })
  }
  return url.toString()
}

/** Parse a non-OK response into a human-readable message + structured body. */
async function parseErrorBody(
  res: Response,
): Promise<{ message: string; body: ApiErrorBody }> {
  let body: ApiErrorBody = {}
  try {
    body = (await res.json()) as ApiErrorBody
  } catch {
    /* ignore parse error */
  }
  const rawMessage = body.detail ?? body.message ?? body.error
  const message =
    typeof rawMessage === 'string' ? rawMessage : `HTTP ${res.status}`
  return { message, body }
}

/** True when a 401 response signals that the access token simply expired. */
function isAccessTokenExpired(
  status: number,
  body: ApiErrorBody,
  message: string,
): boolean {
  if (status !== 401) return false
  if (body.code === 'ACCESS_TOKEN_EXPIRED') return true
  return /access token has expired|token is expired|token.*expired/i.test(
    `${body.message ?? ''} ${message}`,
  )
}

async function request<T>(
  baseUrl: string,
  method: HttpMethod,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { auth = true, body, params, timeoutMs = 8000, isRetry = false } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const res = await fetch(buildUrl(baseUrl, path, params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: baseUrl === AUTH_BASE_URL ? 'include' : 'same-origin',
      signal: controller.signal,
    })

    if (!res.ok) {
      const { message, body: errBody } = await parseErrorBody(res)

      // Access token expired → silently refresh once, then replay the request.
      if (
        auth &&
        !isRetry &&
        getToken() &&
        isAccessTokenExpired(res.status, errBody, message)
      ) {
        const newToken = await refreshAccessToken()
        if (newToken) {
          return request<T>(baseUrl, method, path, { ...options, isRetry: true })
        }
        // Refresh failed (cookie missing/expired/revoked) → end the session below.
      }

      const invalidTokenResponse =
        res.status === 401 ||
        (res.status === 403 && /invalid token|invalid credentials|validate credentials/i.test(message))
      if (auth && getToken() && invalidTokenResponse) {
        redirectToLoginForInvalidToken()
      }

      throw new Error(message)
    }

    // 204 No Content
    if (res.status === 204) return undefined as unknown as T

    return (await res.json()) as Promise<T>
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Service request timed out (5s). Please check your connection and try again.', {
        cause: err,
      })
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

// ─── Convenience factories ────────────────────────────────────────────────────

/** Call the AuthenApp service (Python / FastAPI). Default 5s timeout. */
export function authRequest<T>(
  method: HttpMethod,
  path: string,
  options?: RequestOptions,
): Promise<T> {
  return request<T>(AUTH_BASE_URL, method, path, {
    timeoutMs: 5000,
    ...options,
  })
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
 * Build a form-encoded fetch call (used for OAuth2 password flow).
 * Enforces a strict 5000ms timeout.
 */
export async function formRequest<T>(
  baseUrl: string,
  path: string,
  fields: Record<string, string>,
  timeoutMs: number = 5000,
): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const body = new URLSearchParams(fields)
    const res = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
      credentials: 'include',
      signal: controller.signal,
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

    return (await res.json()) as Promise<T>
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Authentication service timed out (5s). Server did not respond in time.', {
        cause: err,
      })
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}
