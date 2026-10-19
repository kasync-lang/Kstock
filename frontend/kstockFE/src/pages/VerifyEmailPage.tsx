import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { verifyEmail } from '../services/auth.service'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const initialToken = searchParams.get('token') || ''

  const [token, setToken] = useState(initialToken)
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [verified, setVerified] = useState(false)

  useEffect(() => {
    let isMounted = true
    if (initialToken) {
      verifyEmail(initialToken.trim())
        .then((res) => {
          if (isMounted) {
            setVerified(true)
            setStatusMessage(res.message || 'Email verified successfully.')
            setLoading(false)
          }
        })
        .catch((err) => {
          if (isMounted) {
            setErrorMessage(
              err instanceof Error
                ? err.message
                : 'Failed to verify email. The token may be expired or invalid.',
            )
            setLoading(false)
          }
        })
    }
    return () => {
      isMounted = false
    }
  }, [initialToken])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token.trim()) return

    setLoading(true)
    setErrorMessage(null)
    setStatusMessage(null)

    try {
      const res = await verifyEmail(token.trim())
      setVerified(true)
      setStatusMessage(res.message || 'Email verified successfully.')
    } catch (err) {
      console.error(err)
      setErrorMessage(
        err instanceof Error
          ? err.message
          : 'Failed to verify email. The token may be expired or invalid.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Email verification"
      subtitle="Confirm your email to complete registration and secure your Kstock account."
    >
      <div className="login-form">
        <div className="form-header">
          <h2>Verify email</h2>
          <p>Activate your account to access all features.</p>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#abb5cb' }}>
            <p>Verifying your email token...</p>
          </div>
        )}

        {verified && (
          <div>
            <div style={{ padding: '16px', background: 'rgba(52, 194, 147, 0.1)', border: '1px solid rgba(52, 194, 147, 0.3)', borderRadius: '12px', color: '#68e6c0', fontSize: '14px', marginBottom: '16px' }}>
              {statusMessage || 'Your email has been verified successfully! You can now sign in.'}
            </div>
            <Link to="/login" className="primary-button" style={{ display: 'block', textAlign: 'center', textDecoration: 'none' }}>
              Proceed to Sign in
            </Link>
          </div>
        )}

        {!loading && !verified && (
          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '16px' }}>
            {errorMessage && (
              <div style={{ padding: '10px 14px', background: 'rgba(239, 83, 80, 0.15)', border: '1px solid rgba(239, 83, 80, 0.4)', borderRadius: '8px', color: '#ff8a9a', fontSize: '13px' }}>
                {errorMessage}
              </div>
            )}

            <label className="field">
              <span>Verification token</span>
              <input
                type="text"
                name="token"
                placeholder="Paste token from email"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
              />
            </label>

            <button type="submit" className="primary-button" disabled={loading || !token.trim()}>
              {loading ? 'Verifying...' : 'Verify account'}
            </button>

            <p className="helper">
              Already verified? <Link to="/login">Sign in</Link>
            </p>
          </form>
        )}
      </div>
    </AuthLayout>
  )
}

