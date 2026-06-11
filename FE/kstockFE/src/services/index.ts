/**
 * Barrel re-export — import everything from '@/services'
 *
 * Usage:
 *   import { login, getSymbols, buyStock } from '../services'
 */

// Base client utilities (token helpers, etc.)
export { getToken, setToken, removeToken, API_BASE_URL, AUTH_BASE_URL } from './api'

// Auth (AuthenApp)
export * from './auth.service'

// Symbols
export * from './symbol.service'

// Favorites / Watchlist
export * from './favorite.service'

// Notes
export * from './note.service'

// Alerts
export * from './alert.service'

// Portfolio assets
export * from './asset.service'

// Buy / Sell transactions
export * from './transaction.service'

// Live price WebSocket feed
export * from './socket.service'
