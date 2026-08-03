/**
 * WebSocket service
 * Backend: InteractionApp (Go/Gin) — /api/ws
 *
 * The server pushes live stock price updates as JSON messages after upgrading
 * the connection via gorilla/websocket.
 */

import { API_BASE_URL, getToken } from './api'

export interface PriceUpdate {
  symbol: string
  price: number
  timestamp?: string
}

export type PriceUpdateCallback = (update: PriceUpdate) => void
export type ErrorCallback = (event: Event) => void
export type CloseCallback = (event: CloseEvent) => void

/**
 * Open a WebSocket connection to the live price feed.
 *
 * The access token is appended as a query parameter because the WebSocket API
 * does not support custom headers in the browser.
 *
 * @returns A cleanup function that closes the socket.
 *
 * @example
 * const close = connectPriceFeed(
 *   (update) => console.log(update.symbol, update.price),
 *   (err)    => console.error(err),
 * )
 * // Later:
 * close()
 */
export function connectPriceFeed(
  onMessage: PriceUpdateCallback,
  onError?: ErrorCallback,
  onClose?: CloseCallback,
): () => void {
  const wsBase = API_BASE_URL.replace(/^http/, 'ws')
  const token = getToken()
  const url = token ? `${wsBase}/ws?token=${token}` : `${wsBase}/ws`

  const socket = new WebSocket(url)

  socket.onmessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as PriceUpdate
      onMessage(data)
    } catch {
      // Non-JSON frames are silently ignored
    }
  }

  if (onError) socket.onerror = onError
  if (onClose) socket.onclose = onClose

  return () => socket.close()
}
