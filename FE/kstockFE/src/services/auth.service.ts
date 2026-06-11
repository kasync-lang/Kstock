/**
 * Authentication service
 * Backend: AuthenApp (FastAPI) — base prefix /api/v1
 */

import { AUTH_BASE_URL, authRequest, formRequest, setToken, removeToken } from './api'
import type { Token, UserPublic, UserRegister, NewPassword, Message } from '../types'

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
  console.log("token", token)
  console.log("token.access_token", token.access_token)
  setToken(token.access_token)
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
 * Log the user out by clearing the stored token.
 */
export function logout(): void {
  removeToken()
}
