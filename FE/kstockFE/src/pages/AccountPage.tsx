import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import {
  getAllNotes,
  getMe,
  updateMe,
  updateMyPassword,
  updateNote,
  deleteNote,
} from '../services'
import type { NoteDetail, UserPublic } from '../types'
import { useFavorites } from '../context'
import { formatAuthError } from '../utils/authErrors'
import './AccountPage.css'

type AccountTab = 'profile' | 'favorites' | 'notes'

interface FormStatus {
  type: 'success' | 'error' | 'info'
  text: string
}

const ACCOUNT_TABS: AccountTab[] = ['profile', 'favorites', 'notes']

function isAccountTab(value: string | null): value is AccountTab {
  return value !== null && ACCOUNT_TABS.includes(value as AccountTab)
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
}

export default function AccountPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab: AccountTab = isAccountTab(requestedTab) ? requestedTab : 'profile'

  const [user, setUser] = useState<UserPublic | null>(null)
  const { favorites } = useFavorites()
  const [notes, setNotes] = useState<NoteDetail[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Profile Form state
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMessage, setProfileMessage] = useState<FormStatus | null>(null)
  const [passwordMessage, setPasswordMessage] = useState<FormStatus | null>(null)

  // Note edit state
  const [editingNote, setEditingNote] = useState<NoteDetail | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [noteMessage, setNoteMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    async function fetchTabData() {
      try {
        if (activeTab === 'profile') {
          const currentUser = await getMe()
          if (isMounted) {
            setUser(currentUser)
            setLoading(false)
          }
        } else if (activeTab === 'notes') {
          const response = await getAllNotes()
          if (isMounted) {
            setNotes(response.data ?? [])
            setLoading(false)
          }
        } else {
          if (isMounted) setLoading(false)
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            formatAuthError(requestError, 'Unable to load account data.'),
          )
          setLoading(false)
        }
      }
    }

    fetchTabData()
    return () => {
      isMounted = false
    }
  }, [activeTab])

  const selectTab = (tab: AccountTab) => {
    setLoading(true)
    setError(null)
    setSearchParams(tab === 'profile' ? {} : { tab })
    setProfileMessage(null)
    setPasswordMessage(null)
    setNoteMessage(null)
    setEditingNote(null)
  }

  const isOAuthUser = Boolean(user?.provider && user.provider.toLowerCase() !== 'local')

  const handleProfileSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    setSavingProfile(true)
    setProfileMessage(null)

    try {
      const updatedUser = await updateMe({
        email: String(formData.get('email') ?? ''),
        full_name: String(formData.get('fullName') ?? ''),
      })
      setUser(updatedUser)
      setProfileMessage({
        type: 'success',
        text: 'Profile updated successfully.',
      })
    } catch (requestError) {
      setProfileMessage({
        type: 'error',
        text: formatAuthError(requestError, 'Unable to update profile.'),
      })
    } finally {
      setSavingProfile(false)
    }
  }

  const handlePasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const newPassword = String(formData.get('newPassword') ?? '')
    const confirmPassword = String(formData.get('confirmPassword') ?? '')

    if (newPassword !== confirmPassword) {
      setPasswordMessage({
        type: 'error',
        text: 'Confirmation password does not match new password.',
      })
      return
    }

    try {
      const response = await updateMyPassword({
        current_password: String(formData.get('currentPassword') ?? ''),
        new_password: newPassword,
      })
      event.currentTarget.reset()
      setPasswordMessage({
        type: 'success',
        text: response.message || 'Password updated successfully.',
      })
    } catch (requestError) {
      setPasswordMessage({
        type: 'error',
        text: formatAuthError(requestError, 'Unable to update password.'),
      })
    }
  }

  const handleStartEditNote = (note: NoteDetail) => {
    setEditingNote(note)
    setEditTitle(note.title)
    setEditContent(note.content)
    setNoteMessage(null)
  }

  const handleCancelEditNote = () => {
    setEditingNote(null)
    setEditTitle('')
    setEditContent('')
  }

  const handleSaveEditNote = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!editingNote) return

    setSavingNote(true)
    setNoteMessage(null)
    try {
      await updateNote({
        id: editingNote.id,
        title: editTitle.trim(),
        content: editContent.trim(),
      })

      // Update state locally
      setNotes(
        (prev) =>
          prev?.map((n) =>
            n.id === editingNote.id
              ? {
                  ...n,
                  title: editTitle.trim(),
                  content: editContent.trim(),
                  updated_at: new Date().toISOString(),
                }
              : n,
          ) || null,
      )
      setEditingNote(null)
      setNoteMessage('Note updated successfully.')
    } catch (err) {
      console.error(err)
      setNoteMessage(err instanceof Error ? err.message : 'Failed to update note.')
    } finally {
      setSavingNote(false)
    }
  }

  const handleDeleteNote = async (noteId: string) => {
    try {
      await deleteNote(noteId)
      setNotes((prev) => prev?.filter((n) => n.id !== noteId) || null)
      if (editingNote?.id === noteId) {
        handleCancelEditNote()
      }
    } catch (err) {
      console.error(err)
      setNoteMessage(err instanceof Error ? err.message : 'Failed to delete note.')
    }
  }

  return (
    <AppLayout>
      <main className="account-page">
        <header className="account-header">
          <div>
            <p className="account-kicker">Personal workspace</p>
            <h1>Account Settings</h1>
          </div>
        </header>

        <div className="account-layout">
          <nav className="account-tabs" aria-label="Account sections">
            {ACCOUNT_TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                className={activeTab === tab ? 'active' : ''}
                onClick={() => selectTab(tab)}
              >
                {tab === 'profile' ? 'Profile' : tab === 'favorites' ? 'Watchlist' : 'Notes'}
              </button>
            ))}
          </nav>

          <section className="account-content" aria-live="polite">
            {loading && <p className="account-status">Loading account data...</p>}
            {!loading && error && <p className="account-error">{error}</p>}

            {!loading && !error && activeTab === 'profile' && user && (
              <div className="account-section">
                <div className="account-section-heading">
                  <h2>
                    Personal Information
                    {isOAuthUser ? (
                      <span className="account-badge google">
                        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
                          <path
                            fill="#4285F4"
                            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                          />
                          <path
                            fill="#34A853"
                            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                          />
                          <path
                            fill="#FBBC05"
                            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                          />
                          <path
                            fill="#EA4335"
                            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                          />
                        </svg>
                        Google OAuth
                      </span>
                    ) : (
                      <span className="account-badge local">Standard</span>
                    )}
                  </h2>
                  <p>Stored securely in the authentication service.</p>
                </div>

                {isOAuthUser && (
                  <div className="account-alert info" role="status" style={{ marginBottom: '16px' }}>
                    <svg
                      className="account-alert-icon"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    <span>
                      Your profile information is synchronized with Google. Changes to your name or email are managed directly via your Google Account.
                    </span>
                  </div>
                )}

                <form className="account-form" onSubmit={handleProfileSubmit}>
                  <label>
                    <span>Full name</span>
                    <input
                      name="fullName"
                      defaultValue={user.full_name ?? ''}
                      disabled={isOAuthUser}
                      required
                    />
                  </label>
                  <label>
                    <span>Email</span>
                    <input
                      type="email"
                      name="email"
                      defaultValue={user.email}
                      disabled={isOAuthUser}
                      required
                    />
                  </label>
                  {!isOAuthUser && (
                    <button type="submit" disabled={savingProfile}>
                      {savingProfile ? 'Saving...' : 'Save profile'}
                    </button>
                  )}
                  {profileMessage && (
                    <div className={`account-alert ${profileMessage.type}`} role="alert">
                      <svg
                        className="account-alert-icon"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        {profileMessage.type === 'success' ? (
                          <polyline points="20 6 9 17 4 12" />
                        ) : (
                          <>
                            <circle cx="12" cy="12" r="10" />
                            <line x1="12" y1="8" x2="12" y2="12" />
                            <line x1="12" y1="16" x2="12.01" y2="16" />
                          </>
                        )}
                      </svg>
                      <span>{profileMessage.text}</span>
                    </div>
                  )}
                </form>

                <div className="account-section-heading account-password-heading">
                  <h2>Change Password</h2>
                </div>

                {isOAuthUser ? (
                  <div className="account-oauth-box">
                    <svg
                      viewBox="0 0 24 24"
                      width="22"
                      height="22"
                      aria-hidden="true"
                      style={{ flexShrink: 0, marginTop: '2px' }}
                    >
                      <path
                        fill="#4285F4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                      />
                    </svg>
                    <div>
                      <strong>Google Sign-In Account</strong>
                      <p style={{ margin: '4px 0 0', color: '#abb5cb', fontSize: '13.5px' }}>
                        OAuth accounts authenticated via Google do not have a local password. Authentication is managed securely through Google SSO.
                      </p>
                    </div>
                  </div>
                ) : (
                  <form className="account-form" onSubmit={handlePasswordSubmit}>
                    <label>
                      <span>Current password</span>
                      <input
                        type="password"
                        name="currentPassword"
                        autoComplete="current-password"
                        required
                        minLength={4}
                      />
                    </label>
                    <label>
                      <span>New password</span>
                      <input
                        type="password"
                        name="newPassword"
                        autoComplete="new-password"
                        required
                        minLength={4}
                      />
                    </label>
                    <label>
                      <span>Confirm new password</span>
                      <input
                        type="password"
                        name="confirmPassword"
                        autoComplete="new-password"
                        required
                        minLength={4}
                      />
                    </label>
                    <button type="submit">Update password</button>
                    {passwordMessage && (
                      <div className={`account-alert ${passwordMessage.type}`} role="alert">
                        <svg
                          className="account-alert-icon"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          {passwordMessage.type === 'success' ? (
                            <polyline points="20 6 9 17 4 12" />
                          ) : (
                            <>
                              <circle cx="12" cy="12" r="10" />
                              <line x1="12" y1="8" x2="12" y2="12" />
                              <line x1="12" y1="16" x2="12.01" y2="16" />
                            </>
                          )}
                        </svg>
                        <span>{passwordMessage.text}</span>
                      </div>
                    )}
                  </form>
                )}
              </div>
            )}

            {!loading && !error && activeTab === 'favorites' && (
              <div className="account-section">
                <div className="account-section-heading">
                  <h2>Watchlist</h2>
                  <p>
                    {favorites.length} symbol{favorites.length === 1 ? '' : 's'} in your watchlist.
                  </p>
                </div>
                {favorites.length === 0 ? (
                  <p className="account-status">No favorite symbols yet.</p>
                ) : (
                  <div className="favorite-grid">
                    {favorites.map((symbol) => (
                      <button
                        key={symbol}
                        type="button"
                        onClick={() => navigate(`/stock/${encodeURIComponent(symbol)}`)}
                      >
                        {symbol}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!loading && !error && activeTab === 'notes' && notes && (
              <div className="account-section">
                <div className="account-section-heading">
                  <h2>Research Notes</h2>
                  <p>
                    {notes.length} saved note{notes.length === 1 ? '' : 's'}.
                  </p>
                </div>

                {noteMessage && <p className="account-message">{noteMessage}</p>}

                {notes.length === 0 ? (
                  <p className="account-status">No notes created yet.</p>
                ) : (
                  <div className="note-list">
                    {notes.map((note) => (
                      <article key={note.id} className="account-note">
                        <button
                          type="button"
                          className="note-symbol"
                          onClick={() => navigate(`/stock/${encodeURIComponent(note.symbol)}`)}
                        >
                          {note.symbol}
                        </button>
                        <div>
                          <h3>{note.title}</h3>
                          <p>{note.content}</p>
                          <time>{formatDate(note.updated_at || note.created_at)}</time>
                          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                            <button
                              type="button"
                              onClick={() => handleStartEditNote(note)}
                              style={{
                                padding: '4px 10px',
                                fontSize: '12px',
                                background: '#1b2540',
                                color: '#edf2ff',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '4px',
                                cursor: 'pointer',
                              }}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteNote(note.id)}
                              style={{
                                padding: '4px 10px',
                                fontSize: '12px',
                                background: 'rgba(239, 83, 80, 0.15)',
                                color: '#ff9da8',
                                border: '1px solid rgba(239, 83, 80, 0.3)',
                                borderRadius: '4px',
                                cursor: 'pointer',
                              }}
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                )}

                {editingNote && (
                  <div style={{ marginTop: '24px', padding: '20px', background: '#0a0f1d', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                    <h3 style={{ margin: '0 0 14px' }}>Edit Note: {editingNote.symbol}</h3>
                    <form onSubmit={handleSaveEditNote} style={{ display: 'grid', gap: '12px' }}>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        placeholder="Note title"
                        required
                        style={{
                          padding: '10px',
                          background: '#101726',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: '6px',
                          color: '#fff',
                        }}
                      />
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        placeholder="Note content"
                        rows={4}
                        required
                        style={{
                          padding: '10px',
                          background: '#101726',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: '6px',
                          color: '#fff',
                          fontFamily: 'inherit',
                          resize: 'vertical',
                        }}
                      />
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button
                          type="submit"
                          disabled={savingNote}
                          style={{
                            padding: '8px 16px',
                            background: '#23b9d5',
                            color: '#07101b',
                            border: 'none',
                            borderRadius: '6px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          {savingNote ? 'Saving...' : 'Save Changes'}
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelEditNote}
                          style={{
                            padding: '8px 16px',
                            background: 'transparent',
                            color: '#abb5cb',
                            border: '1px solid rgba(255,255,255,0.15)',
                            borderRadius: '6px',
                            cursor: 'pointer',
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </main>
    </AppLayout>
  )
}
