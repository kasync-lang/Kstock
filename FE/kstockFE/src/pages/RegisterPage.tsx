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
          <input
            type="password"
            name="password"
            placeholder="Enter your password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={!passwordValid}
          />
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
          <input
            type="password"
            name="confirmPassword"
            placeholder="Re-enter your password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            aria-invalid={!passwordsMatch}
          />
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

