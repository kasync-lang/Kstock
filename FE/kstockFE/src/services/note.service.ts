/**
 * Notes service
 * Backend: InteractionApp (Go/Gin) — /api/notes
 */

import { apiRequest } from './api'
import type { NoteCreate, NoteDetail, NotePublic, NoteUpdate, Message } from '../types'

/**
 * GET /api/notes/
 *
 * Fetch every note belonging to the authenticated user.
 */
export function getAllNotes(): Promise<{ data: NoteDetail[] }> {
  return apiRequest<{ data: NoteDetail[] }>('GET', '/notes/')
}

/**
 * GET /api/notes/:symbol
 *
 * Fetch notes for a given symbol (prefix-matched).
 */
export function getNotesBySymbol(
  symbol: string,
): Promise<{ data: NoteDetail[] }> {
  return apiRequest<{ data: NoteDetail[] }>(
    'GET',
    `/notes/${encodeURIComponent(symbol.toUpperCase())}`,
  )
}

/**
 * POST /api/notes/
 *
 * Create a new note. Returns the new note's id and title.
 */
export function createNote(payload: NoteCreate): Promise<{ data: NotePublic }> {
  return apiRequest<{ data: NotePublic }>('POST', '/notes/', { body: payload })
}

/**
 * PUT /api/notes/
 *
 * Update an existing note's title and/or content.
 * Both `title` and `content` are optional (coalesce on the server).
 */
export function updateNote(
  payload: NoteUpdate,
): Promise<{ data: NoteUpdate }> {
  return apiRequest<{ data: NoteUpdate }>('PUT', '/notes/', { body: payload })
}

/**
 * DELETE /api/notes/:note_id
 *
 * Permanently delete a note by its ID.
 */
export function deleteNote(noteId: string): Promise<{ data: boolean }> {
  return apiRequest<{ data: boolean }>(
    'DELETE',
    `/notes/${encodeURIComponent(noteId)}`,
  )
}
