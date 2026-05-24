import type { ReactNode } from 'react'

type AuthLayoutProps = {
  title: string
  subtitle: string
  children: ReactNode
}

function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <main className="login-page">
      <div className="ambient" aria-hidden="true">
        <span className="orb orb-one"></span>
        <span className="orb orb-two"></span>
        <span className="orb orb-three"></span>
      </div>

      <div className="login-shell">
        <section className="brand-panel">
          <div className="brand-badge">KS</div>
          <p className="eyebrow">Kstock Secure Cloud</p>
          <h1>{title}</h1>
          <p className="subtitle">{subtitle}</p>
          <div className="stat-grid">
            <div className="stat-card">
              <p className="stat-title">Uptime</p>
              <p className="stat-value">99.98%</p>
            </div>
            <div className="stat-card">
              <p className="stat-title">Latency</p>
              <p className="stat-value">120ms</p>
            </div>
            <div className="stat-card">
              <p className="stat-title">Regions</p>
              <p className="stat-value">12</p>
            </div>
          </div>
          <div className="tech-row">
            <span>Encrypted sessions</span>
            <span>Adaptive MFA</span>
            <span>Audit-ready</span>
          </div>
        </section>

        <section className="form-panel">{children}</section>
      </div>

      <footer className="login-footer">
        <span>Status: All systems normal</span>
        <span>Last verified 2 minutes ago</span>
      </footer>
    </main>
  )
}

export default AuthLayout


