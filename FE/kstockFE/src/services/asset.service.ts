/**
 * Asset service
 * Backend: InteractionApp (Go/Gin) — /api/assets
 */

import { apiRequest } from './api'
import type { AssetsResponse } from '../types'

/**
 * GET /api/assets/
 *
 * Fetch the authenticated user's portfolio holdings.
 *
 * Each asset includes:
 * - `symbol`          — ticker
 * - `quantity`        — number of shares held
 * - `price`           — average unit cost (book price)
 * - `market_value`    — current market price from the live price store
 * - `profit_and_loss` — unrealised P&L = quantity × (market_value − price)
 *
 * The top-level `all_profit_and_loss` is the sum of all individual P&L values.
 */
export function getAssets(): Promise<AssetsResponse> {
  return apiRequest<AssetsResponse>('GET', '/assets/')
}
