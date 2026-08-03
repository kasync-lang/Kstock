/**
 * Chart service
 * Backend: InteractionApp (Go/Gin) — /api/chart/history
 */

import { apiRequest } from './api'
import type { ChartHistoryQueryParams, OHLCVResponse } from '../types'

/**
 * GET /api/chart/history
 *
 * Fetch historical OHLCV chart data for a given symbol and time frame.
 *
 * @param params Query parameters: symbol, resolution (e.g. '1m', '15m', '1h', '1D'), from (Unix timestamp), to (Unix timestamp)
 * @example
 * const history = await getChartHistory({
 *   symbol: 'IBM',
 *   resolution: '1D',
 *   from: 1784505600,
 *   to: 1784764800,
 * })
 */
export function getChartHistory(
  params: ChartHistoryQueryParams,
): Promise<OHLCVResponse> {
  return apiRequest<OHLCVResponse>('GET', '/chart/history', {
    params: {
      symbol: params.symbol.toUpperCase(),
      resolution: params.resolution,
      from: params.from,
      to: params.to,
    },
  })
}
