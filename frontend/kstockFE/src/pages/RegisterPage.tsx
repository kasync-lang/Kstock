import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { register } from '../services/auth.service'
import { formatAuthError } from '../utils/authErrors'

const passwordRegex = /^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*\W)(?!.* ).{8,}$/

function RegisterPage() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null)

  const passwordValid = !password || passwordRegex.test(password)
  const passwordsMatch = !confirmPassword || password === confirmPassword

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMessage(null)

    if (!passwordRegex.test(password)) {
      setErrorMessage('Password must be at least 8 characters and include uppercase, lowercase, number, and special character.')
      return
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await register({
        email,
        password,
        full_name: fullName.trim() || undefined,
      })
      setRegisteredEmail(email)
    } catch (err) {
      console.error('Registration failed:', err)
      setErrorMessage(formatAuthError(err, 'Registration failed. Please try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  if (registeredEmail) {
    return (
      <AuthLayout
        title="Account created"
        subtitle="Check your inbox to verify your email address before signing in."
      >
        <div className="login-form">
          <div className="form-header">
            <h2>Verify your email</h2>
            <p>We sent a verification link to <strong>{registeredEmail}</strong>.</p>
          </div>

          <div style={{ padding: '16px', background: 'rgba(52, 194, 147, 0.1)', border: '1px solid rgba(52, 194, 147, 0.3)', borderRadius: '12px', color: '#68e6c0', fontSize: '14px', lineHeight: 1.6 }}>
            Please check your spam or inbox folder and click the link to activate your account.
          </div>

          <div style={{ display: 'grid', gap: '10px', marginTop: '12px' }}>
            <Link to="/login" className="primary-button" style={{ textAlign: 'center', textDecoration: 'none' }}>
              Back to Sign in
            </Link>
            <Link to="/verify-email" className="secondary-button" style={{ textAlign: 'center', textDecoration: 'none' }}>
              Enter token manually
            </Link>
          </div>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Register to unlock smart portfolios, market signals, and automated alerts tailored for you."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="form-header">
          <h2>Sign up</h2>
          <p>Use your email to create a secure profile.</p>
        </div>

        {errorMessage && (
          <div style={{ padding: '10px 14px', background: 'rgba(239, 83, 80, 0.15)', border: '1px solid rgba(239, 83, 80, 0.4)', borderRadius: '8px', color: '#ff8a9a', fontSize: '13px' }}>
            {errorMessage}
          </div>
        )}

        <label className="field">
          <span>Full name</span>
          <input
            type="text"
            name="fullName"
            placeholder="Nguyen Van A"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>Email</span>
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

        <label className="field">
          <span>Password</span>
          <div className="input-wrapper">
            <input
              type={showPassword ? 'text' : 'password'}
              name="password"
              placeholder="Enter your password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
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
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
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
          <span>Confirm password</span>
          <div className="input-wrapper">
            <input
              type={showConfirmPassword ? 'text' : 'password'}
              name="confirmPassword"
              placeholder="Re-enter your password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              aria-invalid={!passwordsMatch}
            />
            <button
              type="button"
              className="toggle-password"
              onClick={() => setShowConfirmPassword((prev) => !prev)}
              aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
            >
              {showConfirmPassword ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
          {!passwordsMatch && (
            <span className="field-error">Passwords do not match.</span>
          )}
        </label>

        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>

        <p className="helper">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

export default RegisterPage
