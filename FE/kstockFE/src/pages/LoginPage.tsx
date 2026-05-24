import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'

function LoginPage() {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue monitoring smart portfolios, market signals, and automated alerts."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="form-header">
          <h2>Sign in</h2>
          <p>Use your work email to access the dashboard.</p>
        </div>

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
            autoComplete="current-password"
            required
          />
        </label>

        <div className="form-row">
          <label className="checkbox">
            <input type="checkbox" name="remember" />
            <span>Remember me</span>
          </label>
          <a className="link" href="#">
            Forgot password?
          </a>
        </div>

        <button type="submit" className="primary-button">
          Continue to dashboard
        </button>

        <div className="divider">
          <span>or</span>
        </div>

        <button type="button" className="secondary-button">
          Continue with SSO
        </button>

        <p className="helper">
          New to Kstock? <Link to="/register">Create account</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

export default LoginPage

