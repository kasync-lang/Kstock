/**
 * Transaction service
 * Backend: InteractionApp (Go/Gin) — /api/transactions
 *
 * A single endpoint handles both BUY and SELL orders.
 * The server resolves the live market price from its in-memory price store, so
 * the client never needs to send a price field.
 */

import { apiRequest } from './api'
import type {
  Order,
  BuyOrderResponse,
  SellOrderResponse,
  OrderOperation,
} from '../types'

/**
 * POST /api/transactions/
 *
 * Submit a BUY or SELL order.
 * Returns either a `BuyOrderResponse` or `SellOrderResponse` depending on the
 * `operation` field.
 */
export function submitOrder(
  payload: Order,
): Promise<BuyOrderResponse | SellOrderResponse> {
  return apiRequest<BuyOrderResponse | SellOrderResponse>('POST', '/transactions/', {
    body: payload,
  })
}

/**
 * Convenience wrapper — submit a BUY order.
 */
export function buyStock(
  symbol: string,
  quantity: number,
): Promise<BuyOrderResponse> {
  return submitOrder({ symbol, quantity, operation: 'BUY' }) as Promise<BuyOrderResponse>
}

/**
 * Convenience wrapper — submit a SELL order.
 */
export function sellStock(
  symbol: string,
  quantity: number,
): Promise<SellOrderResponse> {
  return submitOrder({ symbol, quantity, operation: 'SELL' }) as Promise<SellOrderResponse>
}

/**
 * Type guard — check if a transaction response is a BUY result.
 */
export function isBuyResponse(
  res: BuyOrderResponse | SellOrderResponse,
): res is BuyOrderResponse {
  return 'total_cost' in res
}
