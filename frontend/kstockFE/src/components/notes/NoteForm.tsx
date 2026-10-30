import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

export interface NoteFormValues {
  title: string
  content: string
}

interface NoteFormProps {
  initialValues?: NoteFormValues
  submitLabel: string
  saving: boolean
  onSubmit: (values: NoteFormValues) => Promise<boolean> | boolean
  onCancel: () => void
}

const TITLE_MAX_LENGTH = 120

export default function NoteForm({
  initialValues,
  submitLabel,
  saving,
  onSubmit,
  onCancel,
}: NoteFormProps) {
  const [title, setTitle] = useState(initialValues?.title ?? '')
  const [content, setContent] = useState(initialValues?.content ?? '')

  const trimmedTitle = title.trim()
  const trimmedContent = content.trim()
  const unchanged =
    initialValues !== undefined &&
    trimmedTitle === initialValues.title.trim() &&
    trimmedContent === initialValues.content.trim()
  const canSubmit = Boolean(trimmedTitle && trimmedContent) && !unchanged && !saving

  const submit = async () => {
    if (!canSubmit) return
    const saved = await onSubmit({ title: trimmedTitle, content: trimmedContent })
    if (saved && initialValues === undefined) {
      setTitle('')
      setContent('')
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void submit()
  }

  // Ctrl/Cmd+Enter saves, Escape cancels — from either field.
  const handleKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onCancel()
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      void submit()
    }
  }

  return (
    <form className="note-form" onSubmit={handleSubmit} onKeyDown={handleKeyDown}>
      <input
        className="note-form-title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Title, e.g. Q3 earnings thesis"
        maxLength={TITLE_MAX_LENGTH}
        aria-label="Note title"
        autoFocus
      />
      <textarea
        className="note-form-content"
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder="What are you watching for? Entry/exit levels, catalysts, risks..."
        aria-label="Note content"
        rows={5}
      />
      <div className="note-form-footer">
        <span className="note-form-hint">
          <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to save · <kbd>Esc</kbd> to cancel
        </span>
        <div className="note-form-actions">
          <button type="button" className="note-btn note-btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="note-btn note-btn-primary" disabled={!canSubmit}>
            {saving ? 'Saving...' : submitLabel}
          </button>
        </div>
      </div>
    </form>
  )
}
