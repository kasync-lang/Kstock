import type { NoteDetail } from '../../types'

function noteTimestamp(note: NoteDetail): number {
  const time = new Date(note.updated_at || note.created_at).getTime()
  return Number.isNaN(time) ? 0 : time
}

/** Newest first — the API returns notes in no particular order. */
export function sortNotesNewestFirst(notes: NoteDetail[]): NoteDetail[] {
  return [...notes].sort((a, b) => noteTimestamp(b) - noteTimestamp(a))
}

/** The by-symbol endpoint is prefix-matched (e.g. "A" also returns "AAPL"), so keep exact matches only. */
export function filterNotesForSymbol(notes: NoteDetail[], symbol: string): NoteDetail[] {
  const target = symbol.toUpperCase()
  return notes.filter((note) => note.symbol.toUpperCase() === target)
}

export function formatNoteTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  const diffSeconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (diffSeconds < 60) return 'Just now'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`
  if (diffSeconds < 7 * 86400) return `${Math.floor(diffSeconds / 86400)}d ago`

  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatNoteFullTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
}
