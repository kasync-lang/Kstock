/**
 * Symbol service
 * Backend: InteractionApp (Go/Gin) — /api/symbols
 */

import { apiRequest } from './api'
import type { QuerySymbol, SymbolPublic, SymbolBaseDetail } from '../types'

/**
 * GET /api/symbols
 *
 * Search / list symbols with optional filters.
 *
 * @example
 * const results = await getSymbols({ name: 'AAPL', exchange: 'NASDAQ', order_by: 'name' })
 */
export function getSymbols(
  query: QuerySymbol = {},
): Promise<{ data: SymbolPublic[] }> {
  return apiRequest<{ data: SymbolPublic[] }>('GET', '/symbols', {
    params: query as Record<string, string | undefined>,
  })
}

/**
 * GET /api/symbols/:symbol/detail
 *
 * Retrieve full company profile for a single ticker.
 */
export function getSymbolDetail(
  symbol: string,
): Promise<{ data: SymbolBaseDetail }> {
  return apiRequest<{ data: SymbolBaseDetail }>(
    'GET',
    `/symbols/${encodeURIComponent(symbol.toUpperCase())}/detail`,
  )
}
