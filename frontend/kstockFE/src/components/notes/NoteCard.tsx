import { useState } from 'react'
import type { NoteDetail } from '../../types'
import NoteForm from './NoteForm'
import type { NoteFormValues } from './NoteForm'
import { formatNoteFullTime, formatNoteTime } from './noteUtils'

interface NoteCardProps {
  note: NoteDetail
  editing: boolean
  saving: boolean
  /** Show the symbol chip (useful when notes from several symbols are listed together). */
  showSymbol?: boolean
  onSymbolClick?: (symbol: string) => void
  onStartEdit: () => void
  onCancelEdit: () => void
  onSave: (values: NoteFormValues) => Promise<boolean>
  onDelete: () => Promise<void>
}

/** Content longer than this gets collapsed behind "Show more". */
const COLLAPSE_THRESHOLD = 220

export default function NoteCard({
  note,
  editing,
  saving,
  showSymbol = false,
  onSymbolClick,
  onStartEdit,
  onCancelEdit,
  onSave,
  onDelete,
}: NoteCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const timestamp = note.updated_at || note.created_at
  const isLong = note.content.length > COLLAPSE_THRESHOLD || note.content.split('\n').length > 4

  const handleConfirmDelete = async () => {
    setDeleting(true)
    try {
      await onDelete()
    } finally {
      setDeleting(false)
      setConfirmingDelete(false)
    }
  }

  if (editing) {
    return (
      <article className="note-card note-card-editing">
        {showSymbol && <span className="note-symbol-chip static">{note.symbol}</span>}
        <NoteForm
          initialValues={{ title: note.title, content: note.content }}
          submitLabel="Save changes"
          saving={saving}
          onSubmit={onSave}
          onCancel={onCancelEdit}
        />
      </article>
    )
  }

  return (
    <article className="note-card">
      <header className="note-card-header">
        <div className="note-card-heading">
          {showSymbol && (
            <button
              type="button"
              className="note-symbol-chip"
              onClick={() => onSymbolClick?.(note.symbol)}
              title={`Open ${note.symbol} chart`}
            >
              {note.symbol}
            </button>
          )}
          <h3 className="note-card-title">{note.title}</h3>
        </div>
        <time className="note-card-time" dateTime={timestamp} title={formatNoteFullTime(timestamp)}>
          {formatNoteTime(timestamp)}
        </time>
      </header>

      <p className={`note-card-content${isLong && !expanded ? ' collapsed' : ''}`}>
        {note.content}
      </p>
      {isLong && (
        <button
          type="button"
          className="note-link-btn"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}

      <footer className="note-card-footer">
        {confirmingDelete ? (
          <div className="note-confirm" role="alertdialog" aria-label="Confirm delete">
            <span>Delete this note?</span>
            <button
              type="button"
              className="note-btn note-btn-ghost"
              onClick={() => setConfirmingDelete(false)}
              disabled={deleting}
              autoFocus
            >
              Keep
            </button>
            <button
              type="button"
              className="note-btn note-btn-danger"
              onClick={handleConfirmDelete}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        ) : (
          <div className="note-card-actions">
            <button
              type="button"
              className="note-icon-btn"
              onClick={onStartEdit}
              aria-label={`Edit note: ${note.title}`}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
              </svg>
              Edit
            </button>
            <button
              type="button"
              className="note-icon-btn danger"
              onClick={() => setConfirmingDelete(true)}
              aria-label={`Delete note: ${note.title}`}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 6h18" />
                <path d="M8 6V4h8v2" />
                <path d="M19 6l-1 14H6L5 6" />
              </svg>
              Delete
            </button>
          </div>
        )}
      </footer>
    </article>
  )
}
