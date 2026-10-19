import type { SymbolPreview } from '../types'
import type { TransformedItem } from './chart'

export interface QuoteDetails {
  currentPrice: number
  previousClose: number
  priceChange: number
  percentChange: number
  isPositive: boolean
}

/**
 * Calculates current price, dollar change, and percent change for a stock quote.
 *
 * Ensures consistent calculation between SymbolListPage and StockDetailPage:
 * 1. Base price & baseline previous close are derived from SymbolPreview:
 *    - previousClose = basePrice / (1 + percentChange / 100)
 * 2. If a live tick arrives, liveTick.price updates currentPrice and change is
 *    calculated against previousClose.
 * 3. If SymbolPreview is not available, falls back to chart historical items.
 */
export function calculateQuoteDetails(params: {
  symbolPreview?: SymbolPreview | null
  livePrice?: number | null
  items?: TransformedItem[]
}): QuoteDetails {
  const { symbolPreview, livePrice, items = [] } = params

  const hasLive = typeof livePrice === 'number' && Number.isFinite(livePrice) && livePrice > 0

  if (symbolPreview && typeof symbolPreview.lastPrice === 'number' && symbolPreview.lastPrice > 0) {
    const basePrice = symbolPreview.lastPrice
    const basePercentChange =
      typeof symbolPreview.percentChange === 'number' && Number.isFinite(symbolPreview.percentChange)
        ? symbolPreview.percentChange
        : 0

    // Baseline previous close price
    let previousClose = basePrice
    if (basePercentChange !== -100) {
      previousClose = basePrice / (1 + basePercentChange / 100)
    }

    if (hasLive) {
      const currentPrice = livePrice!
      const priceChange =
        previousClose > 0 ? currentPrice - previousClose : basePrice > 0 ? currentPrice - basePrice : 0
      const percentChange =
        previousClose > 0
          ? (priceChange / previousClose) * 100
          : basePrice > 0
            ? (priceChange / basePrice) * 100
            : 0

      return {
        currentPrice,
        previousClose,
        priceChange,
        percentChange,
        isPositive: priceChange >= 0,
      }
    }

    // No live tick: use exact values from symbolPreview
    const currentPrice = basePrice
    const priceChange =
      previousClose > 0 ? currentPrice - previousClose : basePrice * (basePercentChange / 100)
    const percentChange = basePercentChange

    return {
      currentPrice,
      previousClose,
      priceChange,
      percentChange,
      isPositive: priceChange >= 0,
    }
  }

  // Fallback when symbolPreview is unavailable (e.g. from chart history bars)
  const latestItem = items.length > 0 ? items[items.length - 1] : null
  const currentPrice = hasLive ? livePrice! : latestItem ? latestItem.close : 0
  const previousItem = items.length >= 2 ? items[items.length - 2] : null
  const previousClose = previousItem ? previousItem.close : latestItem ? latestItem.open : 0

  const priceChange = previousClose > 0 ? currentPrice - previousClose : 0
  const percentChange = previousClose > 0 ? (priceChange / previousClose) * 100 : 0

  return {
    currentPrice,
    previousClose,
    priceChange,
    percentChange,
    isPositive: priceChange >= 0,
  }
}

