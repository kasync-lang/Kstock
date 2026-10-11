import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { exchangeOAuthCode, getGoogleCallback } from '../services/auth.service'
import { setToken } from '../services/api'

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isCancelled = false

    async function processCallback() {
      // 1. Check if token was directly provided in query parameters
      const directToken =
        searchParams.get('session_token') ||
        searchParams.get('access_token') ||
        searchParams.get('token')

      if (directToken) {
        setToken(directToken)
        if (window.opener) {
          window.opener.postMessage(
            {
              type: 'GOOGLE_AUTH_SUCCESS',
              session_token: directToken,
              access_token: directToken,
            },
            '*',
          )
          window.close()
          return
        }
        navigate('/symbols', { replace: true })
        return
      }

      // 2. Check for OAuth exchange code or state
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const errorParam = searchParams.get('error')

      if (errorParam) {
        if (!isCancelled) {
          setError(`Google authorization failed: ${errorParam}`)
        }
        return
      }

      if (!code) {
        if (!isCancelled) {
          setError('Missing authorization code parameter from authentication service.')
        }
        return
      }

      try {
        // Exchange one-time authorization code for access token via /oauth/exchange
        let token
        try {
          token = await exchangeOAuthCode(code)
        } catch (exchangeErr) {
          // If state is also present, attempt legacy callback as fallback
          if (state) {
            token = await getGoogleCallback(code, state)
          } else {
            throw exchangeErr
          }
        }

        const tokenStr = token.access_token || token.session_token
        if (tokenStr && window.opener) {
          window.opener.postMessage(
            {
              type: 'GOOGLE_AUTH_SUCCESS',
              session_token: tokenStr,
              access_token: tokenStr,
            },
            '*',
          )
          window.close()
          return
        }

        if (!isCancelled) {
          navigate('/symbols', { replace: true })
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Failed to complete code exchange with server.',
          )
        }
      }
    }

    processCallback()

    return () => {
      isCancelled = true
    }
  }, [navigate, searchParams])

  return (
    <AuthLayout
      title={error ? 'Authentication error' : 'Exchanging access token...'}
      subtitle={
        error
          ? 'An error occurred during authentication exchange.'
          : 'Please wait while we exchange your code for an access token.'
      }
    >
      <div className="auth-form-wrapper" style={{ textAlign: 'center', padding: '16px 0' }}>
        {error ? (
          <div className="auth-form">
            <div className="auth-alert error" role="alert">
              <svg
                className="auth-alert-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{error}</span>
            </div>
            <Link
              to="/login"
              className="auth-submit-btn"
              style={{ textDecoration: 'none', display: 'flex', marginTop: '12px' }}
            >
              Return to sign in
            </Link>
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '16px',
              padding: '24px 0',
            }}
          >
            <span
              className="auth-spinner"
              style={{ width: '36px', height: '36px', borderWidth: '3px' }}
            />
            <p style={{ color: '#abb5cb', fontSize: '14.5px', margin: 0 }}>
              Exchanging code for resource access token...
            </p>
          </div>
        )}
      </div>
    </AuthLayout>
  )
}
