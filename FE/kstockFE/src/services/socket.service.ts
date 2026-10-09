/**
 * WebSocket service
 * Backend: InteractionApp (Go/Gin) — /api/ws/price
 *
 * The server pushes live stock price updates as JSON messages after upgrading
 * the connection via gorilla/websocket.
 */

import { API_BASE_URL, getToken } from './api'

export interface PriceUpdate {
  symbol: string
  price: number
  timestamp?: number | string
  volume?: number
}

export type PriceUpdateCallback = (update: PriceUpdate) => void
export type ErrorCallback = (event: Event) => void
export type CloseCallback = (event: CloseEvent) => void
export type OpenCallback = (event: Event) => void

export interface PriceFeedConnection {
  close: () => void
  subscribe: (symbol: string) => void
  unsubscribe: (symbol: string) => void
  getSocket: () => WebSocket | null
}

export function getWebSocketUrl(): string {
  let wsUrl = API_BASE_URL
  if (!wsUrl.startsWith('http://') && !wsUrl.startsWith('https://') && !wsUrl.startsWith('ws://') && !wsUrl.startsWith('wss://')) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsUrl = `${protocol}//${window.location.host}${wsUrl.startsWith('/') ? '' : '/'}${wsUrl}`
  } else {
    wsUrl = wsUrl.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')
  }

  // Ensure path points to /ws/price
  if (!wsUrl.endsWith('/ws/price')) {
    wsUrl = wsUrl.replace(/\/ws\/?$/, '')
    wsUrl = `${wsUrl}/socket/ws/price`
  }

  const token = getToken()
  return token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl
}

/**
 * Open a WebSocket connection to the live price feed.
 *
 * @returns A PriceFeedConnection object with subscribe, unsubscribe, and close helpers.
 */
export function connectPriceFeed(
  onMessage: PriceUpdateCallback,
  onError?: ErrorCallback,
  onClose?: CloseCallback,
  onOpen?: OpenCallback,
): PriceFeedConnection {
  const url = getWebSocketUrl()
  let socket: WebSocket | null = null

  try {
    socket = new WebSocket(url)
  } catch (err) {
    console.warn('WebSocket connection failed to initialize:', err)
    if (onError) {
      window.setTimeout(() => onError(new Event('error')), 0)
    }
    if (onClose) {
      window.setTimeout(
        () =>
          onClose(
            new CloseEvent('close', {
              wasClean: false,
              code: 1006,
              reason: err instanceof Error ? err.message : 'Initialization failed',
            }),
          ),
        0,
      )
    }
  }

  if (socket) {
    socket.onopen = (event: Event) => {
      if (onOpen) onOpen(event)
    }

    socket.onmessage = (event: MessageEvent) => {
      try {
        const raw = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
        if (raw && typeof raw === 'object') {
          // Check for Tick format { p, s, t, v } or PriceUpdate format { symbol, price }
          const symbol = (raw.s ?? raw.symbol ?? '').toUpperCase()
          const price = typeof raw.p === 'number' ? raw.p : typeof raw.price === 'number' ? raw.price : 0
          if (symbol && price > 0) {
            onMessage({
              symbol,
              price,
              timestamp: raw.t ?? raw.timestamp,
              volume: raw.v ?? raw.volume,
            })
          }
        }
      } catch {
        // Non-JSON frames are silently ignored
      }
    }

    if (onError) socket.onerror = onError
    if (onClose) socket.onclose = onClose
  }

  const subscribe = (symbol: string) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ type: 'subscribe', symbol: symbol.toUpperCase() }))
      } catch (err) {
        console.warn('Failed to send subscribe message:', err)
      }
    }
  }

  const unsubscribe = (symbol: string) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ type: 'unsubscribe', symbol: symbol.toUpperCase() }))
      } catch (err) {
        console.warn('Failed to send unsubscribe message:', err)
      }
    }
  }

  const close = () => {
    if (socket) {
      try {
        // Detach listeners so manual close doesn't trigger unexpected error/reconnect flows
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null
        socket.close()
      } catch {
        // Ignore close error
      }
      socket = null
    }
  }

  return {
    close,
    subscribe,
    unsubscribe,
    getSocket: () => socket,
  }
}
