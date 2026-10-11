import { useContext, useEffect, useMemo } from 'react'
import { LivePriceContext } from './livePrice.context'
import type { LivePriceContextType, ConnectionStatus } from './livePrice.context'

export function useLivePrices(symbolsToSubscribe?: string[]) {
  const context = useContext(LivePriceContext)
  if (!context) {
    throw new Error('useLivePrices must be used within a LivePriceProvider')
  }

  const { subscribe, unsubscribe } = context

  const symbolsKey = useMemo(() => {
    if (!symbolsToSubscribe || symbolsToSubscribe.length === 0) return ''
    return Array.from(
      new Set(symbolsToSubscribe.map((s) => s.trim().toUpperCase()).filter(Boolean)),
    )
      .sort()
      .join(',')
  }, [symbolsToSubscribe])

  useEffect(() => {
    if (!symbolsKey) return
    const list = symbolsKey.split(',')

    subscribe(list)

    return () => {
      unsubscribe(list)
    }
  }, [symbolsKey, subscribe, unsubscribe])

  return context
}

export type { LivePriceContextType, ConnectionStatus }

