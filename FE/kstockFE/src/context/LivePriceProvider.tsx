import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import type { ReactNode } from 'react'
import { connectPriceFeed } from '../services/socket.service'
import type { PriceFeedConnection, PriceUpdate } from '../services/socket.service'
import { LivePriceContext } from './livePrice.context'
import type { ConnectionStatus } from './livePrice.context'

const INITIAL_BACKOFF_MS = 1500
const MAX_BACKOFF_MS = 30000
const BACKOFF_MULTIPLIER = 1.8
const JITTER_MAX_MS = 500

export function LivePriceProvider({ children }: { children: ReactNode }) {
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({})
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const connectionRef = useRef<PriceFeedConnection | null>(null)
  const subCountsRef = useRef<Map<string, number>>(new Map())
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const isConnectingRef = useRef(false)
  const connectFeedRef = useRef<() => void>(() => {})

  const handlePriceUpdate = useCallback((update: PriceUpdate) => {
    setPrices((prev) => ({
      ...prev,
      [update.symbol.toUpperCase()]: update,
    }))
  }, [])

  const getTotalSubscribers = useCallback(() => {
    let total = 0
    subCountsRef.current.forEach((count) => {
      total += count
    })
    return total
  }, [])

  const scheduleReconnect = useCallback(() => {
    // Only schedule reconnect if there are active subscriptions
    if (getTotalSubscribers() === 0) {
      return
    }

    if (reconnectTimerRef.current !== null) {
      return
    }

    const attempt = reconnectAttemptsRef.current
    const delay = Math.min(
      INITIAL_BACKOFF_MS * Math.pow(BACKOFF_MULTIPLIER, attempt) + Math.random() * JITTER_MAX_MS,
      MAX_BACKOFF_MS,
    )
    reconnectAttemptsRef.current += 1

    console.info(
      `[LivePrice] WebSocket disconnected. Retrying in ${(delay / 1000).toFixed(1)}s (attempt ${attempt + 1})...`,
    )

    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null
      if (getTotalSubscribers() > 0) {
        connectFeedRef.current()
      }
    }, delay)
  }, [getTotalSubscribers])

  const connectFeed = useCallback(() => {
    // Only connect if there are active symbol subscriptions
    if (getTotalSubscribers() === 0) {
      if (connectionRef.current) {
        connectionRef.current.close()
        connectionRef.current = null
      }
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      isConnectingRef.current = false
      setStatus('disconnected')
      return
    }

    if (connectionRef.current || isConnectingRef.current) {
      return
    }

    isConnectingRef.current = true
    setStatus('connecting')

    const conn = connectPriceFeed(
      handlePriceUpdate,
      () => {
        isConnectingRef.current = false
        setStatus('error')
      },
      () => {
        isConnectingRef.current = false
        connectionRef.current = null
        setStatus('disconnected')

        // Schedule reconnect with exponential backoff if there are still active subscriptions
        scheduleReconnect()
      },
      () => {
        isConnectingRef.current = false
        // Reset backoff on successful connection
        reconnectAttemptsRef.current = 0
        if (reconnectTimerRef.current !== null) {
          window.clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
        setStatus('connected')
        // Re-subscribe all active symbols on connect
        subCountsRef.current.forEach((count, symbol) => {
          if (count > 0) {
            conn.subscribe(symbol)
          }
        })
      },
    )

    connectionRef.current = conn
  }, [handlePriceUpdate, getTotalSubscribers, scheduleReconnect])

  useEffect(() => {
    connectFeedRef.current = connectFeed
  }, [connectFeed])

  const subscribe = useCallback(
    (symbols: string | string[]) => {
      const list = Array.isArray(symbols) ? symbols : [symbols]
      const validSymbols = list.map((s) => s.trim().toUpperCase()).filter(Boolean)
      if (validSymbols.length === 0) return

      const wasEmpty = getTotalSubscribers() === 0

      validSymbols.forEach((upper) => {
        const current = subCountsRef.current.get(upper) || 0
        subCountsRef.current.set(upper, current + 1)

        if (current === 0 && connectionRef.current) {
          connectionRef.current.subscribe(upper)
        }
      })

      if (wasEmpty) {
        // Fresh subscription session — reset backoff and connect immediately
        reconnectAttemptsRef.current = 0
        if (reconnectTimerRef.current !== null) {
          window.clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
        connectFeed()
      } else if (!connectionRef.current && !reconnectTimerRef.current && !isConnectingRef.current) {
        connectFeed()
      }
    },
    [connectFeed, getTotalSubscribers],
  )

  const unsubscribe = useCallback(
    (symbols: string | string[]) => {
      const list = Array.isArray(symbols) ? symbols : [symbols]
      const validSymbols = list.map((s) => s.trim().toUpperCase()).filter(Boolean)
      if (validSymbols.length === 0) return

      const conn = connectionRef.current

      validSymbols.forEach((upper) => {
        const current = subCountsRef.current.get(upper) || 0
        if (current <= 1) {
          subCountsRef.current.delete(upper)
          if (conn) {
            conn.unsubscribe(upper)
          }
        } else {
          subCountsRef.current.set(upper, current - 1)
        }
      })

      // If no active subscriptions remain, close connection and cancel backoff
      if (getTotalSubscribers() === 0) {
        if (reconnectTimerRef.current !== null) {
          window.clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
        reconnectAttemptsRef.current = 0
        isConnectingRef.current = false
        if (connectionRef.current) {
          connectionRef.current.close()
          connectionRef.current = null
        }
        setStatus('disconnected')
      }
    },
    [getTotalSubscribers],
  )

  useEffect(() => {
    return () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (connectionRef.current) {
        connectionRef.current.close()
        connectionRef.current = null
      }
    }
  }, [])

  const getPrice = useCallback(
    (symbol: string) => {
      return prices[symbol.toUpperCase()]?.price
    },
    [prices],
  )

  const value = useMemo(
    () => ({
      prices,
      status,
      subscribe,
      unsubscribe,
      getPrice,
    }),
    [prices, status, subscribe, unsubscribe, getPrice],
  )

  return <LivePriceContext.Provider value={value}>{children}</LivePriceContext.Provider>
}
