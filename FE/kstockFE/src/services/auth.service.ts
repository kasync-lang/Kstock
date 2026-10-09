/**
 * Authentication service
 * Backend: AuthenApp (FastAPI) — base prefix /api/v1
 */

import { AUTH_BASE_URL, AUTH_ROOT_URL, authRequest, formRequest, setToken, removeToken, getToken } from './api'
import type { Token, UserPublic, UserRegister, NewPassword, Message, UserUpdateMe, UpdatePassword } from '../types'

/**
 * POST /login/access-token
 *
 * OAuth2 password flow — submits as application/x-www-form-urlencoded.
 * Automatically stores the returned JWT in localStorage.
 */
export async function login(email: string, password: string): Promise<Token> {
  const token = await formRequest<Token>(AUTH_BASE_URL, '/login/access-token', {
    username: email, // FastAPI OAuth2PasswordRequestForm uses `username`
    password,
  })
  const accessToken = token.session_token || token.access_token
  setToken(accessToken)
  return token
}

/**
 * POST /signup
 *
 * Register a new user account. A verification email is sent in the background.
 */
export function register(payload: UserRegister): Promise<UserPublic> {
  return authRequest<UserPublic>('POST', '/signup', { auth: false, body: payload })
}

/**
 * GET /signup-verify?token=<token>
 *
 * Verify email address using the token received via email.
 */
export function verifyEmail(token: string): Promise<Message> {
  return authRequest<Message>('GET', '/signup-verify', {
    auth: false,
    params: { token },
  })
}

/**
 * POST /login/test-token
 *
 * Validate the stored access token and return the current user's profile.
 */
export function getMe(): Promise<UserPublic> {
  return authRequest<UserPublic>('POST', '/login/test-token')
}

/** Update the current user's profile in AuthenApp. */
export function updateMe(payload: UserUpdateMe): Promise<UserPublic> {
  return authRequest<UserPublic>('PATCH', '/user/me', { body: payload })
}

/** Change the current user's AuthenApp password. */
export function updateMyPassword(payload: UpdatePassword): Promise<Message> {
  return authRequest<Message>('PATCH', '/user/me/password', { body: payload })
}

/**
 * POST /password-recovery/{email}
 *
 * Trigger a password-reset email.
 */
export function requestPasswordReset(email: string): Promise<Message> {
  return authRequest<Message>('POST', `/password-recovery/${encodeURIComponent(email)}`, {
    auth: false,
  })
}

/**
 * POST /reset-password
 *
 * Set a new password using the reset token received by email.
 */
export function resetPassword(payload: NewPassword): Promise<Message> {
  return authRequest<Message>('POST', '/reset-password', { auth: false, body: payload })
}

/**
 * GET /auth/google
 *
 * URL to initiate Google OAuth 2.0 authentication flow with AuthenApp.
 */
export function getGoogleAuthUrl(): string {
  return `${AUTH_ROOT_URL}/auth/google`
}

/**
 * POST /oauth/exchange
 *
 * Exchange temporary one-time authorization code for access token.
 */
export async function exchangeOAuthCode(code: string): Promise<Token> {
  const url = `${AUTH_ROOT_URL}/oauth/exchange?code=${encodeURIComponent(code)}`
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 8000)

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
      credentials: 'include', // store the HttpOnly refresh-token cookie
      signal: controller.signal,
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

    const data = (await res.json()) as Token
    const tokenStr = data.session_token || data.access_token
    if (tokenStr) {
      setToken(tokenStr)
    }
    return data
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('OAuth code exchange timed out. Please try again.', { cause: err })
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * GET /auth/google/callback
 *
 * Legacy exchange authorization code and state for access/session token.
 */
export async function getGoogleCallback(code: string, state: string): Promise<Token> {
  const url = `${AUTH_ROOT_URL}/auth/google/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 8000)

  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include', // vital to forward oauth_state and oauth_code_verifier cookies
      signal: controller.signal,
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

    const data = (await res.json()) as Token
    const tokenStr = data.session_token || data.access_token
    if (tokenStr) {
      setToken(tokenStr)
    }
    return data
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Google authentication timed out. Please try again.', { cause: err })
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * Trigger Google OAuth 2.0 popup login and wait for callback / session token.
 */
export async function loginWithGoogle(): Promise<Token> {
  const authUrl = getGoogleAuthUrl()

  return new Promise((resolve, reject) => {
    const width = 520
    const height = 640
    const left = window.screenX + (window.outerWidth - width) / 2
    const top = window.screenY + (window.outerHeight - height) / 2.5

    const popup = window.open(
      authUrl,
      'kstock_google_login',
      `width=${width},height=${height},left=${left},top=${top},status=no,resizable=yes`,
    )

    if (!popup) {
      // If popup is blocked by browser, fallback to full page redirect
      window.location.href = authUrl
      return
    }

    let resolved = false

    const handleMessage = (event: MessageEvent) => {
      if (
        event.data &&
        (event.data.type === 'GOOGLE_AUTH_SUCCESS' || event.data.type === 'OAUTH_SUCCESS')
      ) {
        const tokenStr = event.data.session_token || event.data.access_token || event.data.token
        if (tokenStr) {
          resolved = true
          window.removeEventListener('message', handleMessage)
          clearInterval(pollTimer)
          try {
            popup.close()
          } catch {
            /* ignore */
          }
          setToken(tokenStr)
          resolve({ access_token: tokenStr, session_token: tokenStr })
        }
      }
    }

    window.addEventListener('message', handleMessage)

    const pollTimer = setInterval(async () => {
      if (!popup || popup.closed) {
        clearInterval(pollTimer)
        window.removeEventListener('message', handleMessage)
        if (!resolved) {
          const currentToken = getToken()
          if (currentToken) {
            resolve({ access_token: currentToken, session_token: currentToken })
          } else {
            reject(new Error('Google sign-in was cancelled.'))
          }
        }
        return
      }

      try {
        if (popup.location.href) {
          // Check if popup reached /oauth/exchange?code=...
          if (popup.location.pathname.includes('/oauth/exchange')) {
            const params = new URLSearchParams(popup.location.search)
            const exchangeCode = params.get('code')
            if (exchangeCode) {
              resolved = true
              clearInterval(pollTimer)
              window.removeEventListener('message', handleMessage)
              try {
                popup.close()
              } catch {
                /* ignore */
              }
              try {
                const token = await exchangeOAuthCode(exchangeCode)
                resolve(token)
              } catch (err) {
                reject(err)
              }
              return
            }
          }

          // Check if popup reached legacy callback with json response
          if (
            popup.location.pathname.includes('/auth/google/callback') ||
            popup.location.pathname.includes('/auth/callback')
          ) {
            const bodyText = popup.document.body.innerText
            try {
              const data = JSON.parse(bodyText)
              const tokenStr = data.session_token || data.access_token || data.token
              if (tokenStr) {
                resolved = true
                clearInterval(pollTimer)
                window.removeEventListener('message', handleMessage)
                try {
                  popup.close()
                } catch {
                  /* ignore */
                }
                setToken(tokenStr)
                resolve({ access_token: tokenStr, session_token: tokenStr })
              }
            } catch {
              // Content not yet ready
            }
          }
        }
      } catch {
        // Cross-origin while redirecting through Google domain
      }
    }, 500)
  })
}

/**
 * POST /auth/logout
 *
 * Revokes the server-side session (Redis) and clears the HttpOnly refresh
 * cookie, then removes the locally stored access token.
 *
 * Best-effort: local cleanup always runs even if the request fails, so the user
 * is never stuck in a half-logged-in state.
 */
export async function logout(): Promise<void> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 4000)

  try {
    await fetch(`${AUTH_ROOT_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      signal: controller.signal,
    })
  } catch {
    /* best-effort — ignore network errors */
  } finally {
    clearTimeout(timeoutId)
    removeToken()
  }
}
