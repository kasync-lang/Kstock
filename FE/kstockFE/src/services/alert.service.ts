/**
 * Alerts service
 * Backend: InteractionApp (Go/Gin) — /api/alerts
 */

import { apiRequest } from './api'
import type { AlertCreate, AlertDetail, Message } from '../types'

/**
 * POST /api/alerts/
 *
 * Create a new price alert with one or more trigger conditions.
 * Returns the generated alert ID.
 */
export function createAlert(payload: AlertCreate): Promise<{ id: string }> {
  return apiRequest<{ id: string }>('POST', '/alerts/', { body: payload })
}

/**
 * GET /api/alerts/:symbol
 *
 * Retrieve all alerts the current user has set for a given symbol.
 *
 * The server returns `{ data: <raw json> }` — the `data` field is the alert
 * object (or null when no alerts exist for that symbol).
 */
export function getAlertsBySymbol(
  symbol: string,
): Promise<{ data: AlertDetail | null }> {
  return apiRequest<{ data: AlertDetail | null }>(
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
