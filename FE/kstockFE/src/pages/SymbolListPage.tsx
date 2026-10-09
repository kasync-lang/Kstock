import { useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import { getSymbols } from '../services'
import type { SymbolPreview } from '../types'
import { useLivePrices } from '../context'
import { calculateQuoteDetails } from '../utils/quote'
import './SymbolListPage.css'

const MAX_SYMBOLS = 150
const SYMBOLS_PER_PAGE = 40

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatPrice(value: number): string {
  if (!Number.isFinite(value)) return '--'
  return `$${value.toFixed(2)}`
}

export default function SymbolListPage() {
  const navigate = useNavigate()
  const [symbols, setSymbols] = useState<SymbolPreview[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [currentPage, setCurrentPage] = useState<number>(1)

  const reloadSymbols = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const requests = [
        getSymbols({ exchange: 'NASDAQ', order_by: 'name' }),
        getSymbols({ exchange: 'NYSE', order_by: 'name' }),
      ]
      const responses = await Promise.all(requests)
      const uniqueSymbols = Array.from(
        new Map(
          responses
            .flatMap((response) => response.data ?? [])
            .map((symbol) => [symbol.ticker, symbol]),
        ).values(),
      )
      setSymbols(uniqueSymbols.slice(0, MAX_SYMBOLS))
    } catch (err) {
      console.error('Failed to load symbols:', err)
      setError(err instanceof Error ? err.message : 'Failed to load symbols')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    async function fetchSymbols() {
      try {
        const requests = [
          getSymbols({ exchange: 'NASDAQ', order_by: 'name' }),
          getSymbols({ exchange: 'NYSE', order_by: 'name' }),
        ]
        const responses = await Promise.all(requests)
        const uniqueSymbols = Array.from(
          new Map(
            responses
              .flatMap((response) => response.data ?? [])
              .map((symbol) => [symbol.ticker, symbol]),
          ).values(),
        )
        if (isMounted) {
          setSymbols(uniqueSymbols.slice(0, MAX_SYMBOLS))
          setLoading(false)
        }
      } catch (err) {
        console.error('Failed to load symbols:', err)
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to load symbols')
          setLoading(false)
        }
      }
    }

    fetchSymbols()
    return () => {
      isMounted = false
    }
  }, [])

  const handleSymbolClick = (symbol: SymbolPreview) => {
    navigate(`/stock/${encodeURIComponent(symbol.ticker.toUpperCase())}`, {
      state: { symbolPreview: symbol },
    })
  }

  const normalizedSearchTerm = searchTerm.trim().toUpperCase()
  const visibleSymbols = normalizedSearchTerm
    ? symbols.filter(
        (symbol) =>
          symbol.ticker.toUpperCase().includes(normalizedSearchTerm) ||
          symbol.name.toUpperCase().includes(normalizedSearchTerm),
      )
    : symbols
  const totalPages = Math.max(1, Math.ceil(visibleSymbols.length / SYMBOLS_PER_PAGE))
  const pageStart = (currentPage - 1) * SYMBOLS_PER_PAGE
  const rawPageSymbols = visibleSymbols.slice(pageStart, pageStart + SYMBOLS_PER_PAGE)

  // Read live prices without initiating WebSocket subscription on the list page
  const { prices } = useLivePrices()

  // Overlay live tick prices in memory using synchronized quote calculation
  const pageSymbols = useMemo(() => {
    return rawPageSymbols.map((item) => {
      const liveTick = prices[item.ticker.toUpperCase()]
      const quote = calculateQuoteDetails({
        symbolPreview: item,
        livePrice: liveTick?.price,
      })
      return {
        ...item,
        lastPrice: quote.currentPrice,
        percentChange: quote.percentChange,
      }
    })
  }, [rawPageSymbols, prices])

  const handleSearchChange = (value: string) => {
    setSearchTerm(value)
    setCurrentPage(1)
  }

  const changePage = (page: number) => {
    setCurrentPage(Math.min(Math.max(page, 1), totalPages))
  }

  return (
    <AppLayout>
      <div className="symbol-list-page">
        <header className="symbol-list-header">
          <div>
            <p className="market-kicker">Live market overview</p>
            <h1>Explore stocks</h1>
            <p className="market-subtitle">
              Prices and daily movement across {symbols.length || 150} listed companies.
            </p>
          </div>
          <div className="symbol-header-actions">
            <label className="symbol-search">
              <span className="visually-hidden">Filter stocks</span>
              <input
                type="search"
                value={searchTerm}
                onChange={(event) => handleSearchChange(event.target.value)}
                placeholder="Filter by name or symbol"
              />
            </label>
          </div>
        </header>

        <div className="market-toolbar">
          <span className="symbol-count">
            {loading
              ? 'Loading market data...'
              : `${pageStart + 1}-${Math.min(
                  pageStart + SYMBOLS_PER_PAGE,
                  visibleSymbols.length,
                )} of ${visibleSymbols.length} symbols`}
          </span>
          <span className="price-note">NASDAQ and NYSE · USD · 2 decimal places</span>
        </div>

        {loading && (
          <ul className="symbol-list" aria-label="Loading stock symbols" aria-busy="true">
            {Array.from({ length: 18 }).map((_, index) => (
              <li key={`skeleton-${index}`} className="symbol-card symbol-card-skeleton" aria-hidden="true">
                <div className="skeleton-box skeleton-logo" />
                <div className="symbol-info">
                  <div className="skeleton-box skeleton-ticker" />
                  <div className="skeleton-box skeleton-name" />
                </div>
                <div className="skeleton-box skeleton-price" />
                <div className="skeleton-box skeleton-change" />
              </li>
            ))}
          </ul>
        )}

        {error && (
          <div className="symbol-list-error">
            <p>{error}</p>
            <button onClick={reloadSymbols}>Try again</button>
          </div>
        )}

        {!loading && !error && visibleSymbols.length === 0 && (
          <p className="symbol-list-status">No symbols match “{searchTerm}”.</p>
        )}

        {!loading && !error && pageSymbols.length > 0 && (
          <>
            <ul className="symbol-list">
              {pageSymbols.map((symbol) => {
                const movement =
                  symbol.percentChange > 0
                    ? 'positive'
                    : symbol.percentChange < 0
                    ? 'negative'
                    : 'neutral'
                return (
                  <li
                    key={symbol.ticker}
                    className="symbol-card"
                    onClick={() => handleSymbolClick(symbol)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        handleSymbolClick(symbol)
                      }
                    }}
                  >
                    <div className="symbol-logo" aria-hidden="true">
                      {symbol.logo ? (
                        <img src={symbol.logo} alt="" loading="lazy" />
                      ) : (
                        symbol.ticker.slice(0, 1)
                      )}
                    </div>
                    <div className="symbol-info">
                      <div className="symbol-title">
                        <span className="symbol-ticker">{symbol.ticker}</span>
                        <span className="symbol-name">{symbol.name}</span>
                      </div>
                    </div>
                    <span className="symbol-price">{formatPrice(symbol.lastPrice)}</span>
                    <span className={`symbol-change ${movement}`}>
                      {formatPercent(symbol.percentChange)}
                    </span>
                  </li>
                )
              })}
            </ul>
            <nav className="symbol-pagination" aria-label="Symbol list pages">
              <button
                type="button"
                onClick={() => changePage(currentPage - 1)}
                disabled={currentPage === 1}
              >
                Previous
              </button>
              <span>
                Page {currentPage} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => changePage(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                Next
              </button>
            </nav>
          </>
        )}
      </div>
    </AppLayout>
  )
}
