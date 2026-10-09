import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import './AuthLayout.css'

type AuthLayoutProps = {
  title: string
  subtitle?: string
  children: ReactNode
}

function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="auth-page">
      {/* Background ambient lighting */}
      <div className="auth-ambient" aria-hidden="true">
        <div className="auth-glow auth-glow-1" />
        <div className="auth-glow auth-glow-2" />
        <div className="auth-grid-overlay" />
      </div>

      {/* Main card container */}
      <main className="auth-main-content">
        <div className="auth-card">
          <header className="auth-header">
            <Link to="/" className="auth-logo-link" aria-label="Kstock Home">
              <div className="auth-brand-badge">
                <span className="auth-logo-icon">KS</span>
                <div className="auth-badge-glow" />
              </div>
            </Link>
            <h1 className="auth-title">{title}</h1>
            {subtitle && <p className="auth-subtitle">{subtitle}</p>}
          </header>

          <div className="auth-body">{children}</div>
        </div>
      </main>

      {/* Pinned footer at bottom of page */}
      <footer className="auth-legal-footer">
        <a href="/privacy.html" target="_blank" rel="noopener noreferrer">
          Privacy Policy
        </a>
        <span className="auth-footer-dot">&bull;</span>
        <a href="/terms.html" target="_blank" rel="noopener noreferrer">
          Terms of Service
        </a>
      </footer>
    </div>
  )
}

export default AuthLayout
