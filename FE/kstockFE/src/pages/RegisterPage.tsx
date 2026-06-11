import type { FormEvent } from 'react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'

const passwordRegex = /^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*\W)(?!.* ).{8,}$/

function RegisterPage() {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordValid, setPasswordValid] = useState(true)
  const [passwordChecking, setPasswordChecking] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  useEffect(() => {
    if (!password) {
      setPasswordValid(true)
      setPasswordChecking(false)
      return
    }

    setPasswordChecking(true)
    const timer = window.setTimeout(() => {
      setPasswordValid(passwordRegex.test(password))
      setPasswordChecking(false)
    }, 1000)

    return () => window.clearTimeout(timer)
  }, [password])

  const passwordsMatch = !confirmPassword || password === confirmPassword

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Register to unlock smart portfolios, market signals, and automated alerts tailored for you."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="form-header">
          <h2>Sign up</h2>
          <p>Use your work email to create a secure profile.</p>
        </div>

        <label className="field">
          <span>Full name</span>
          <input
            type="text"
            name="fullName"
            placeholder="Nguyen Van A"
            autoComplete="name"
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
              onClick={() => setShowPassword(prev => !prev)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? (
                // Eye-off icon
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                // Eye icon
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
          </div>
          <span className="field-hint">
            Must be 8+ chars, include upper, lower, number, and symbol.
          </span>
          {!passwordValid && !passwordChecking && (
            <span className="field-error">
              Password does not meet complexity requirements.
            </span>
          )}
          {passwordChecking && (
            <span className="field-hint">Checking password strength...</span>
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
              onClick={() => setShowConfirmPassword(prev => !prev)}
              aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
            >
              {showConfirmPassword ? (
                // Eye-off icon
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                // Eye icon
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
          </div>
          {!passwordsMatch && (
            <span className="field-error">Passwords do not match.</span>
          )}
        </label>

        <div className="form-row">
          <label className="checkbox">
            <input type="checkbox" name="remember" />
            <span>Agree to terms</span>
          </label>
          <a className="link" href="#">
            View policy
          </a>
        </div>

        <button type="submit" className="primary-button">
          Create account
        </button>

        <div className="divider">
          <span>or</span>
        </div>

        <button type="button" className="secondary-button">
          Continue with SSO
        </button>

        <p className="helper">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

export default RegisterPage

