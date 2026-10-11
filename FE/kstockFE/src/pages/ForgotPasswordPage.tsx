import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { requestPasswordReset } from '../services/auth.service'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await requestPasswordReset(email)
      setSubmitted(true)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Unable to send password recovery email.')
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <AuthLayout
        title="Check your inbox"
        subtitle="We sent password reset instructions to your email."
      >
        <div className="login-form">
          <div className="form-header">
            <h2>Recovery email sent</h2>
            <p>If an account exists for <strong>{email}</strong>, you will receive a reset link shortly.</p>
          </div>

          <div style={{ padding: '16px', background: 'rgba(52, 194, 147, 0.1)', border: '1px solid rgba(52, 194, 147, 0.3)', borderRadius: '12px', color: '#68e6c0', fontSize: '14px', lineHeight: 1.6 }}>
            Check your spam folder if you do not see it within a few minutes.
          </div>

          <div style={{ display: 'grid', gap: '10px', marginTop: '12px' }}>
            <Link to="/login" className="primary-button" style={{ textAlign: 'center', textDecoration: 'none' }}>
              Return to Sign in
            </Link>
            <Link to="/reset-password" className="secondary-button" style={{ textAlign: 'center', textDecoration: 'none' }}>
              I have a reset token
            </Link>
          </div>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter your account email to receive a password reset link."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="form-header">
          <h2>Forgot password</h2>
          <p>We'll help you recover your access.</p>
        </div>

        {error && (
          <div style={{ padding: '10px 14px', background: 'rgba(239, 83, 80, 0.15)', border: '1px solid rgba(239, 83, 80, 0.4)', borderRadius: '8px', color: '#ff8a9a', fontSize: '13px' }}>
            {error}
          </div>
        )}

        <label className="field">
          <span>Account email</span>
          <input
            type="email"
            name="email"
            placeholder="you@kstock.com"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? 'Sending link...' : 'Send reset link'}
        </button>

        <p className="helper">
          Remembered your password? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

