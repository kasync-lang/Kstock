/**
 * Alerts service
 * Backend: InteractionApp (Go/Gin) — /api/alerts
 */

import { apiRequest } from './api'
import type { AlertCreate, AlertDetail, AlertUpdate, Message } from '../types'

/**
 * POST /api/alerts/
 *
 * Create a new price alert with one or more trigger conditions joined by a
 * single AND/OR operator (`payload.logic`).
 * Returns the generated alert ID.
 */
export function createAlert(payload: AlertCreate): Promise<{ id: string }> {
  return apiRequest<{ id: string }>('POST', '/alerts/', { body: payload })
}

/**
 * PUT /api/alerts/:alert_id
 *
 * Update an existing alert's active flag, AND/OR logic and/or full set of
 * trigger conditions (`triggers` replaces the previous list when provided).
 */
export function updateAlert(
  payload: AlertUpdate,
): Promise<{ data: { id: string } }> {
  const { id, ...body } = payload
  return apiRequest<{ data: { id: string } }>(
    'PUT',
    `/alerts/${encodeURIComponent(id)}`,
    { body },
  )
}

/**
 * GET /api/alerts/:symbol
 *
 * Retrieve all alerts the current user has set for a given symbol.
 *
 * The server returns `{ data: AlertDetail[] }` — one entry per alert, each with
 * its own `logic` (AND/OR) and ordered `triggers`.
 */
export function getAlertsBySymbol(
  symbol: string,
): Promise<{ data: AlertDetail[] }> {
  return apiRequest<{ data: AlertDetail[] }>(
    'GET',
    `/alerts/${encodeURIComponent(symbol.toUpperCase())}`,
  )
}

/**
 * DELETE /api/alerts/:alert_id
 *
 * Delete a specific alert by its ID.
 * The server responds with 204 No Content on success.
 */
export function deleteAlert(alertId: string): Promise<Message> {
  return apiRequest<Message>(
    'DELETE',
    `/alerts/${encodeURIComponent(alertId)}`,
  )
}
