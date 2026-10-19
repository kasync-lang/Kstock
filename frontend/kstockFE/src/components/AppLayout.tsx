import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { getMe, logout } from '../services/auth.service'
import type { UserPublic } from '../types'
import { useLivePrices } from '../context'
import './AppLayout.css'

interface AppLayoutProps {
  children: ReactNode
}

export default function AppLayout({ children }: AppLayoutProps) {
  const navigate = useNavigate()
  const { status: liveStatus } = useLivePrices()
  const [user, setUser] = useState<UserPublic | null>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let isMounted = true
    getMe()
      .then((data) => {
        if (isMounted) setUser(data)
      })
      .catch(() => {
        // Unauthenticated or guest view
      })
    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const userDisplayName = user?.full_name || user?.email || 'Account'
  const userInitial = userDisplayName.charAt(0).toUpperCase()

  const liveStatusText =
    liveStatus === 'connected'
      ? 'Live'
      : liveStatus === 'connecting'
      ? 'Connecting...'
      : 'Offline'

  return (
    <div className="app-shell">
      <div className="app-ambient" aria-hidden="true">
        <span className="app-glow app-glow-one" />
        <span className="app-glow app-glow-two" />
      </div>

      <header className="app-navbar">
        <div className="app-navbar-left">
          <NavLink to="/symbols" className="app-brand" onClick={() => setMobileNavOpen(false)}>
            <div className="app-brand-badge">KS</div>
            <span>Kstock</span>
          </NavLink>

          <nav className={`app-nav-links ${mobileNavOpen ? 'mobile-open' : ''}`}>
            <NavLink
              to="/symbols"
              className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileNavOpen(false)}
            >
              Market
            </NavLink>
            <NavLink
              to="/portfolio"
              className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileNavOpen(false)}
            >
              Portfolio
            </NavLink>
            <NavLink
              to="/trading"
              className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileNavOpen(false)}
            >
              Trading
            </NavLink>
            <NavLink
              to="/alerts"
              className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileNavOpen(false)}
            >
              Alerts
            </NavLink>
            <NavLink
              to="/account"
              className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileNavOpen(false)}
            >
              Account
            </NavLink>
          </nav>
        </div>

        <div className="app-navbar-right">
          <div className={`live-status-pill ${liveStatus}`} title={`Price Feed: ${liveStatusText}`}>
            <span className="live-status-dot" />
            <span>{liveStatusText}</span>
          </div>

          <div className="app-user-menu" ref={menuRef}>
            <button
              type="button"
              className="app-avatar-btn"
              onClick={() => setUserMenuOpen((prev) => !prev)}
              aria-label="User menu"
              aria-expanded={userMenuOpen}
            >
              {userInitial}
            </button>

            {userMenuOpen && (
              <div className="app-user-dropdown">
                <div className="app-user-dropdown-info">
                  <strong>{userDisplayName}</strong>
                  {user?.email && <span>{user.email}</span>}
                </div>
                <button
                  type="button"
                  className="app-dropdown-item"
                  onClick={() => {
                    setUserMenuOpen(false)
                    navigate('/account')
                  }}
                >
                  Profile & Settings
                </button>
                <button
                  type="button"
                  className="app-dropdown-item"
                  onClick={() => {
                    setUserMenuOpen(false)
                    navigate('/account?tab=favorites')
                  }}
                >
                  Watchlist
                </button>
                <button
                  type="button"
                  className="app-dropdown-item"
                  onClick={() => {
                    setUserMenuOpen(false)
                    navigate('/account?tab=notes')
                  }}
                >
                  Research Notes
                </button>
                <button
                  type="button"
                  className="app-dropdown-item app-dropdown-logout"
                  onClick={handleLogout}
                >
                  Log out
                </button>
              </div>
            )}
          </div>

          <button
            type="button"
            className="app-mobile-menu-btn"
            onClick={() => setMobileNavOpen((prev) => !prev)}
            aria-label="Toggle navigation"
          >
            ☰
          </button>
        </div>
      </header>

      <main className="app-main-content">{children}</main>
    </div>
  )
}
