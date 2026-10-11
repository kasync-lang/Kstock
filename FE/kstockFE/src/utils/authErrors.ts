/**
 * Maps raw backend error messages (from AuthenApp FastAPI service)
 * to user-friendly, descriptive messages explaining the exact condition.
 */
export function formatAuthError(
  error: unknown,
  fallbackMessage = 'An unexpected error occurred.',
): string {
  if (!error) return fallbackMessage

  const raw = error instanceof Error ? error.message : String(error)
  const lower = raw.toLowerCase()

  // OAuth specific interactions
  if (lower.includes('oauth accounts do not have a local password')) {
    return 'This account is authenticated via Google (OAuth2) and does not have a local password. Please use Google Sign-In.'
  }
  if (lower.includes('oauth account profile is managed by its provider')) {
    return 'Your profile is synchronized with Google. Profile updates must be made directly in your Google Account.'
  }

  // Password change interactions
  if (lower.includes('incorrect password')) {
    return 'The current password you entered is incorrect. Please check and try again.'
  }
  if (
    lower.includes('new password can not be the same') ||
    lower.includes('same current password')
  ) {
    return 'The new password cannot be the same as your current password. Please choose a new password.'
  }
  if (lower.includes('passwords do not match')) {
    return 'The confirmation password does not match your new password.'
  }
  if (lower.includes('password too weak')) {
    return 'Password is too weak. Please use at least 8 characters with a mix of letters, numbers, and symbols.'
  }

  // Account existence and verification
  if (
    lower.includes('user with this email already exists') ||
    lower.includes('user already exists')
  ) {
    return 'An account with this email address already exists. If this is you, please sign in instead.'
  }
  if (lower.includes('user is not verified')) {
    return 'Your account email has not been verified yet. Please check your inbox for the activation link.'
  }
  if (lower.includes('inactive user')) {
    return 'This account has been deactivated. Please contact support for assistance.'
  }

  // OAuth exchange and token validation
  if (lower.includes('invalid or expired code')) {
    return 'Your Google authorization code has expired or is invalid. Please try signing in again.'
  }
  if (
    lower.includes('invalid credentials') ||
    lower.includes('could not validate credentials')
  ) {
    return 'Your session has expired or is invalid. Please sign in again.'
  }
  if (lower.includes('superuser can not be deleted yourself')) {
    return 'Administrator accounts cannot be deleted directly through self-service.'
  }

  return raw
}

