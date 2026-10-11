import { createContext } from 'react'
import type { PriceUpdate } from '../services/socket.service'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface LivePriceContextType {
  prices: Record<string, PriceUpdate>
  status: ConnectionStatus
  subscribe: (symbols: string | string[]) => void
  unsubscribe: (symbols: string | string[]) => void
  getPrice: (symbol: string) => number | undefined
}

export const LivePriceContext = createContext<LivePriceContextType | null>(null)

