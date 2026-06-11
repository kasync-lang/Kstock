/**
 * Favorites service
 * Backend: InteractionApp (Go/Gin) — /api/favorites
 */

import { apiRequest } from './api'
import type { FavoritesResponse, Message } from '../types'

/**
 * GET /api/favorites
 *
 * Fetch all watchlisted symbols for the authenticated user.
 */
export function getFavorites(): Promise<FavoritesResponse> {
  return apiRequest<FavoritesResponse>('GET', '/favorites')
}

/**
 * POST /api/favorites/:symbol
 *
 * Add a symbol to the watchlist.
 */
export function addFavorite(symbol: string): Promise<Message> {
  return apiRequest<Message>(
    'POST',
    `/favorites/${encodeURIComponent(symbol.toUpperCase())}`,
  )
}

/**
 * DELETE /api/favorites/:symbol
 *
 * Remove a symbol from the watchlist.
 */
export function removeFavorite(symbol: string): Promise<Message> {
  return apiRequest<Message>(
    'DELETE',
    `/favorites/${encodeURIComponent(symbol.toUpperCase())}`,
  )
}
