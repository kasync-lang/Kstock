import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { resetPassword } from '../services/auth.service'
import { formatAuthError } from '../utils/authErrors'

const passwordRegex = /^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*\W)(?!.* ).{8,}$/

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const initialToken = searchParams.get('token') || ''

  const [token, setToken] = useState(initialToken)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const passwordValid = !newPassword || passwordRegex.test(newPassword)
  const passwordsMatch = !confirmPassword || newPassword === confirmPassword

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)

    if (!token.trim()) {
      setError('Password reset token is required.')
      return
    }

    if (!passwordRegex.test(newPassword)) {
      setError('Password must be at least 8 characters and include uppercase, lowercase, number, and special character.')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await resetPassword({
        token: token.trim(),
        new_password: newPassword,
      })
      setSuccessMessage(res.message || 'Password updated successfully.')
    } catch (err) {
      console.error(err)
      setError(formatAuthError(err, 'Failed to reset password. The token may be expired or invalid.'))
    } finally {
      setLoading(false)
    }
  }

  if (successMessage) {
    return (
      <AuthLayout
        title="Password updated"
        subtitle="Your password has been changed successfully. You can now log in with your new credentials."
      >
        <div className="login-form">
          <div className="form-header">
            <h2>Success</h2>
            <p>{successMessage}</p>
          </div>

          <div style={{ padding: '16px', background: 'rgba(52, 194, 147, 0.1)', border: '1px solid rgba(52, 194, 147, 0.3)', borderRadius: '12px', color: '#68e6c0', fontSize: '14px' }}>
            Your account credentials have been updated securely.
          </div>

          <div style={{ marginTop: '12px' }}>
            <Link to="/login" className="primary-button" style={{ display: 'block', textAlign: 'center', textDecoration: 'none' }}>
              Sign in with new password
            </Link>
          </div>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Create new password"
      subtitle="Enter your recovery token and choose a strong new password."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="form-header">
          <h2>Set new password</h2>
          <p>Please enter your token and new password.</p>
        </div>

        {error && (
          <div style={{ padding: '10px 14px', background: 'rgba(239, 83, 80, 0.15)', border: '1px solid rgba(239, 83, 80, 0.4)', borderRadius: '8px', color: '#ff8a9a', fontSize: '13px' }}>
            {error}
          </div>
        )}

        <label className="field">
          <span>Reset token</span>
          <input
            type="text"
            name="token"
            placeholder="Paste your reset token here"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>New password</span>
          <div className="input-wrapper">
            <input
              type={showPassword ? 'text' : 'password'}
              name="newPassword"
              placeholder="Enter new password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              aria-invalid={!passwordValid}
            />
            <button
              type="button"
              className="toggle-password"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
          <span className="field-hint">
            Must be 8+ chars, include upper, lower, number, and symbol.
          </span>
          {!passwordValid && (
            <span className="field-error">
              Password does not meet complexity requirements.
            </span>
          )}
        </label>

        <label className="field">
          <span>Confirm new password</span>
          <div className="input-wrapper">
            <input
              type={showPassword ? 'text' : 'password'}
              name="confirmPassword"
              placeholder="Confirm new password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              aria-invalid={!passwordsMatch}
            />
          </div>
          {!passwordsMatch && (
            <span className="field-error">Passwords do not match.</span>
          )}
        </label>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? 'Updating password...' : 'Update password'}
        </button>

        <p className="helper">
          Back to <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

