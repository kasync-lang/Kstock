/**
 * Asset service
 * Backend: InteractionApp (Go/Gin) — /api/assets
 */

import { apiRequest } from './api'
import type { AssetsResponse, CashBalanceResponse, TopupResponse } from '../types'

/**
 * GET /api/assets/
 *
 * Fetch the authenticated user's portfolio stock holdings and dedicated cash balance.
 *
 * Each asset includes:
 * - `symbol`          — ticker
 * - `quantity`        — number of shares held
 * - `price`           — average unit cost (book price)
 * - `market_value`    — current market price from the live price store
 * - `profit_and_loss` — unrealised P&L = quantity × (market_value − price)
 *
 * The top-level `all_profit_and_loss` is the sum of all individual P&L values across stock holdings.
 * The top-level `cash_balance` is the uninvested cash amount from the dedicated cash table.
 */
export function getAssets(): Promise<AssetsResponse> {
  return apiRequest<AssetsResponse>('GET', '/assets/')
}

/**
 * GET /api/assets/cash
 *
 * Fetch the authenticated user's available cash balance independently.
 * Lightweight and decoupled from stock holdings and in-memory price stores.
 */
export function getCashBalance(): Promise<CashBalanceResponse> {
  return apiRequest<CashBalanceResponse>('GET', '/assets/cash')
}

/**
 * POST /api/assets/topup
 *
 * Deposit (top-up) USD funds into user's dedicated cash balance.
 */
export function topupAsset(amount: number): Promise<TopupResponse> {
  return apiRequest<TopupResponse>('POST', '/assets/topup', {
    body: { amount },
  })
}

/**
 * Alias for topupAsset reflecting the dedicated cash balance separation.
 */
export const topupCash = topupAsset
