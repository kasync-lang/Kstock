import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { createNote, deleteNote, getNotesBySymbol, updateNote } from '../../services/note.service'
import type { NoteDetail } from '../../types'
import NoteCard from './NoteCard'
import NoteForm from './NoteForm'
import type { NoteFormValues } from './NoteForm'
import { filterNotesForSymbol, sortNotesNewestFirst } from './noteUtils'
import './Notes.css'

interface SymbolNotesPanelProps {
  symbol: string
}

/**
 * Floating "Notes" button + slide-in panel for creating, editing and deleting notes on one symbol.
 * Render with `key={symbol}` so all state resets when the symbol changes.
 */
export default function SymbolNotesPanel({ symbol }: SymbolNotesPanelProps) {
  const [open, setOpen] = useState(false)
  const [notes, setNotes] = useState<NoteDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [composing, setComposing] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadNotes = async () => {
    const response = await getNotesBySymbol(symbol)
    return sortNotesNewestFirst(filterNotesForSymbol(response.data ?? [], symbol))
  }

  useEffect(() => {
    let isMounted = true

    getNotesBySymbol(symbol)
      .then((response) => {
        if (isMounted) {
          setNotes(sortNotesNewestFirst(filterNotesForSymbol(response.data ?? [], symbol)))
        }
      })
      .catch((err) => {
        console.warn('Unable to load notes:', err)
        if (isMounted) setError('Unable to load saved notes.')
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [symbol])

  // Escape closes the panel (the note form handles its own Escape first).
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !composing && !editingId) setOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, composing, editingId])

  const startComposing = () => {
    setEditingId(null)
    setComposing(true)
    setError(null)
  }

  const handleCreate = async ({ title, content }: NoteFormValues) => {
    setSaving(true)
    setError(null)
    try {
      await createNote({ symbol, title, content })
      setNotes(await loadNotes())
      setComposing(false)
      return true
    } catch (err) {
      console.warn('Unable to create note:', err)
      setError('Unable to save note. Your text is still in the form — try again.')
      return false
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async (noteId: string, { title, content }: NoteFormValues) => {
    setSaving(true)
    setError(null)
    try {
      await updateNote({ id: noteId, title, content })
      setNotes((current) =>
        current.map((note) =>
          note.id === noteId
            ? { ...note, title, content, updated_at: new Date().toISOString() }
            : note,
        ),
      )
      setEditingId(null)
      return true
    } catch (err) {
      console.warn('Unable to update note:', err)
      setError('Unable to save changes.')
      return false
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (noteId: string) => {
    setError(null)
    try {
      await deleteNote(noteId)
      setNotes((current) => current.filter((note) => note.id !== noteId))
    } catch (err) {
      console.warn('Unable to delete note:', err)
      setError('Unable to delete note.')
    }
  }

  return (
    <>
      <button
        type="button"
        className={`notes-fab${open ? ' active' : ''}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="symbol-notes-panel"
        title={open ? 'Close notes (Esc)' : `Your notes on ${symbol}`}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
          <path d="M14 3v6h6" />
          <path d="M8 13h8" />
          <path d="M8 17h5" />
        </svg>
        <span>Notes</span>
        {!loading && notes.length > 0 && <span className="notes-fab-count">{notes.length}</span>}
      </button>

      {open && (
        <aside id="symbol-notes-panel" className="notes-panel" aria-label={`Notes for ${symbol}`}>
          <header className="notes-panel-header">
            <div>
              <h2>
                Notes <span className="notes-panel-symbol">{symbol}</span>
              </h2>
              <p>
                {loading
                  ? 'Loading...'
                  : notes.length === 0
                    ? 'No notes yet'
                    : `${notes.length} note${notes.length === 1 ? '' : 's'}`}
              </p>
            </div>
            <button
              type="button"
              className="notes-panel-close"
              onClick={() => setOpen(false)}
              aria-label="Close notes panel"
              title="Close (Esc)"
            >
              ×
            </button>
          </header>

          {composing ? (
            <div className="notes-panel-composer">
              <NoteForm
                submitLabel="Save note"
                saving={saving}
                onSubmit={handleCreate}
                onCancel={() => setComposing(false)}
              />
            </div>
          ) : (
            <button
              type="button"
              className="note-btn note-btn-primary notes-panel-new"
              onClick={startComposing}
              disabled={loading}
            >
              + New note
            </button>
          )}

          {error && (
            <p className="notes-error" role="alert">
              {error}
            </p>
          )}

          <div className="notes-panel-list">
            {loading ? (
              <div className="notes-skeleton" aria-hidden="true">
                <span />
                <span />
              </div>
            ) : notes.length === 0 ? (
              !composing && (
                <div className="notes-empty">
                  <p>Keep your thesis, price targets and catalysts for {symbol} here.</p>
                </div>
              )
            ) : (
              notes.map((note) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  editing={editingId === note.id}
                  saving={saving}
                  onStartEdit={() => {
                    setComposing(false)
                    setEditingId(note.id)
                  }}
                  onCancelEdit={() => setEditingId(null)}
                  onSave={(values) => handleUpdate(note.id, values)}
                  onDelete={() => handleDelete(note.id)}
                />
              ))
            )}
          </div>

          <Link to="/account?tab=notes" className="notes-panel-all">
            View all notes →
          </Link>
        </aside>
      )}
    </>
  )
}
