import { useEffect, useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import { getAssets, getCashBalance, topupAsset, getSymbols } from '../services'
import type { Asset, SymbolPreview } from '../types'
import { useLivePrices } from '../context'
import PortfolioCharts, { type EnrichedHolding } from '../components/portfolio/PortfolioCharts'
import PortfolioTooltip, { type TooltipMetric } from '../components/portfolio/PortfolioTooltip'
import './PortfolioPage.css'

function formatMoney(value: number): string {
  if (!Number.isFinite(value)) return '$0.00'
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '0.00%'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

type FilterStatus = 'all' | 'gainers' | 'losers'
type SortBy = 'value_desc' | 'pnl_desc' | 'pnl_asc' | 'symbol_asc'

export default function PortfolioPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [cashBalance, setCashBalance] = useState(0)
  const [symbolsMap, setSymbolsMap] = useState<Record<string, SymbolPreview>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all')
  const [sortBy, setSortBy] = useState<SortBy>('value_desc')
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  // Deposit modal state
  const [isDepositOpen, setIsDepositOpen] = useState(false)
  const [depositAmount, setDepositAmount] = useState<string>('1000')
  const [depositing, setDepositing] = useState(false)
  const [depositStatus, setDepositStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Floating hover tooltip for table & summary cards
  const [floatingTooltip, setFloatingTooltip] = useState<{
    visible: boolean
    x: number
    y: number
    title: string
    subtitle?: string
    badge?: string
    color: string
    metrics: TooltipMetric[]
    footer?: string
  }>({
    visible: false,
    x: 0,
    y: 0,
    title: '',
    color: '#7c5cff',
    metrics: [],
  })

  // Load portfolio assets & cash
  const loadPortfolio = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [assetsResult, cashResult, symbolsResult] = await Promise.allSettled([
        getAssets(),
        getCashBalance(),
        getSymbols({ exchange: 'NASDAQ' }),
      ])

      let loadedAssets: Asset[] = []
      let loadedCash = 0

      if (assetsResult.status === 'fulfilled') {
        loadedAssets = assetsResult.value.data ?? []
        if (typeof assetsResult.value.cash_balance === 'number') {
          loadedCash = assetsResult.value.cash_balance
        }
      }

      if (cashResult.status === 'fulfilled') {
        loadedCash = cashResult.value.cash_balance
      }

      if (symbolsResult.status === 'fulfilled') {
        const map: Record<string, SymbolPreview> = {}
        symbolsResult.value.data?.forEach((s) => {
          map[s.ticker.toUpperCase()] = s
        })
        setSymbolsMap((prev) => ({ ...prev, ...map }))
      }

      setAssets(loadedAssets)
      setCashBalance(loadedCash)

      if (assetsResult.status === 'rejected' && cashResult.status === 'rejected') {
        throw assetsResult.reason
      }
    } catch (err) {
      console.warn('Unable to load assets from server:', err)
      const msg = err instanceof Error ? err.message : 'Unable to load portfolio assets'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    async function initialFetch() {
      try {
        const [assetsResult, cashResult, symbolsResult] = await Promise.allSettled([
          getAssets(),
          getCashBalance(),
          getSymbols({ exchange: 'NASDAQ' }),
        ])

        if (!isMounted) return

        let loadedAssets: Asset[] = []
        let loadedCash = 0

        if (assetsResult.status === 'fulfilled') {
          loadedAssets = assetsResult.value.data ?? []
          if (typeof assetsResult.value.cash_balance === 'number') {
            loadedCash = assetsResult.value.cash_balance
          }
        }

        if (cashResult.status === 'fulfilled') {
          loadedCash = cashResult.value.cash_balance
        }

        if (symbolsResult.status === 'fulfilled') {
          const map: Record<string, SymbolPreview> = {}
          symbolsResult.value.data?.forEach((s) => {
            map[s.ticker.toUpperCase()] = s
          })
          setSymbolsMap(map)
        }

        setAssets(loadedAssets)
        setCashBalance(loadedCash)
        setLoading(false)

        if (assetsResult.status === 'rejected' && cashResult.status === 'rejected') {
          throw assetsResult.reason
        }
      } catch (err) {
        console.warn('Unable to load assets from server:', err)
        const msg = err instanceof Error ? err.message : 'Unable to load portfolio assets'
        if (isMounted) {
          setError(msg)
          setLoading(false)
        }
      }
    }

    initialFetch()
    return () => {
      isMounted = false
    }
  }, [])

  // Defensive filter to guarantee USD is never treated as a stock holding
  const stockAssets = useMemo(
    () => assets.filter((a) => a.symbol.toUpperCase() !== 'USD'),
    [assets],
  )

  // Extract holding symbols to subscribe to live price ticks
  const stockSymbols = useMemo(
    () => stockAssets.map((a) => a.symbol),
    [stockAssets],
  )
  const { prices } = useLivePrices(stockSymbols)

  // Compute live holding calculations for stocks
  const enrichedHoldings: EnrichedHolding[] = useMemo(() => {
    return stockAssets.map((asset) => {
      const tickerUpper = asset.symbol.toUpperCase()
      const tick = prices[tickerUpper]
      const currentPrice = tick && tick.price > 0 ? tick.price : asset.market_value || asset.price
      const marketValue = asset.quantity * currentPrice
      const costBasis = asset.quantity * asset.price
      const pnl = marketValue - costBasis
      const pnlPercent = costBasis > 0 ? (pnl / costBasis) * 100 : 0
      const preview = symbolsMap[tickerUpper]

      return {
        ...asset,
        name: preview?.name,
        logo: preview?.logo,
        currentPrice,
        marketValue,
        costBasis,
        livePnL: pnl,
        livePnLPercent: pnlPercent,
      }
    })
  }, [stockAssets, prices, symbolsMap])

  // Total Portfolio Value (Net worth = stock holdings + cash)
  const totalValue = useMemo(
    () => enrichedHoldings.reduce((sum, h) => sum + h.marketValue, 0) + cashBalance,
    [enrichedHoldings, cashBalance],
  )

  // Stock cost basis
  const stockCostBasis = useMemo(
    () => enrichedHoldings.reduce((sum, h) => sum + h.costBasis, 0),
    [enrichedHoldings],
  )

  // Unrealized P&L from stocks
  const totalPnL = useMemo(
    () => enrichedHoldings.reduce((sum, h) => sum + h.livePnL, 0),
    [enrichedHoldings],
  )
  const totalPnLPercent = stockCostBasis > 0 ? (totalPnL / stockCostBasis) * 100 : 0
  const pnlClass = totalPnL > 0 ? 'positive' : totalPnL < 0 ? 'negative' : 'neutral'
  const stockCount = stockAssets.length

  // Winners and Losers count
  const gainersCount = useMemo(() => enrichedHoldings.filter((h) => h.livePnL > 0).length, [enrichedHoldings])
  const losersCount = useMemo(() => enrichedHoldings.filter((h) => h.livePnL < 0).length, [enrichedHoldings])

  // Filtered & Sorted Holdings for table display
  const displayedHoldings = useMemo(() => {
    const result = enrichedHoldings.filter((h) => {
      // If a specific symbol was selected from chart
      if (selectedSymbol && h.symbol.toUpperCase() !== selectedSymbol.toUpperCase()) {
        return false
      }

      // Search query (symbol or name)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchesSymbol = h.symbol.toLowerCase().includes(q)
        const matchesName = h.name ? h.name.toLowerCase().includes(q) : false
        if (!matchesSymbol && !matchesName) return false
      }

      // Filter tabs
      if (filterStatus === 'gainers' && h.livePnL <= 0) return false
      if (filterStatus === 'losers' && h.livePnL >= 0) return false

      return true
    })

    // Sorting
    result.sort((a, b) => {
      switch (sortBy) {
        case 'value_desc':
          return b.marketValue - a.marketValue
        case 'pnl_desc':
          return b.livePnLPercent - a.livePnLPercent
        case 'pnl_asc':
          return a.livePnLPercent - b.livePnLPercent
        case 'symbol_asc':
          return a.symbol.localeCompare(b.symbol)
        default:
          return b.marketValue - a.marketValue
      }
    })

    return result
  }, [enrichedHoldings, searchQuery, filterStatus, sortBy, selectedSymbol])

  // Floating Tooltip Handlers
  const handleShowTableTooltip = (
    e: React.MouseEvent,
    holding: EnrichedHolding,
    customField?: 'ticker' | 'cost' | 'price' | 'pnl' | 'weight',
  ) => {
    const weight = totalValue > 0 ? (holding.marketValue / totalValue) * 100 : 0
    let footer = 'Click row to view details or place a trade'
    const metrics: TooltipMetric[] = [
      {
        label: 'Portfolio Weight',
        value: `${weight.toFixed(1)}% Portfolio`,
        highlight: 'accent',
      },
      {
        label: 'Market Value',
        value: formatMoney(holding.marketValue),
        highlight: 'neutral',
      },
      {
        label: 'Shares Held',
        value: `${holding.quantity.toLocaleString()} Shares`,
      },
      {
        label: 'Average Cost',
        value: formatMoney(holding.price),
      },
      {
        label: 'Current Price',
        value: formatMoney(holding.currentPrice),
        highlight: 'accent',
      },
      {
        label: 'Cost Basis',
        value: formatMoney(holding.costBasis),
      },
      {
        label: 'Unrealized P&L',
        value: `${formatMoney(holding.livePnL)} (${formatPercent(holding.livePnLPercent)})`,
        highlight: holding.livePnL > 0 ? 'positive' : holding.livePnL < 0 ? 'negative' : 'neutral',
      },
    ]

    if (customField === 'cost') {
      footer = `Formula: ${holding.quantity.toLocaleString()} shares × ${formatMoney(holding.price)} (Avg Cost)`
    } else if (customField === 'pnl') {
      footer = `Return on Investment (ROI): ${formatPercent(holding.livePnLPercent)} on ${formatMoney(holding.costBasis)} invested`
    } else if (customField === 'weight') {
      footer = `Represents ${weight.toFixed(1)}% of total net worth (${formatMoney(totalValue)})`
    }

    setFloatingTooltip({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      title: holding.symbol,
      subtitle: holding.name || holding.symbol,
      badge: `${weight.toFixed(1)}% Portfolio`,
      color: holding.livePnL >= 0 ? '#53e6b7' : '#ff8a9a',
      metrics,
      footer,
    })
  }

  const handleShowSummaryTooltip = (
    e: React.MouseEvent,
    type: 'networth' | 'cash' | 'cost' | 'pnl',
  ) => {
    let title = ''
    let subtitle = ''
    let footer = ''
    const metrics: TooltipMetric[] = []

    if (type === 'networth') {
      const equityVal = totalValue - cashBalance
      title = 'Total Portfolio Value'
      subtitle = 'Net Worth (Equities + Cash)'
      metrics.push(
        {
          label: 'Stock Holdings',
          value: formatMoney(equityVal),
          highlight: 'accent',
        },
        {
          label: 'Cash Balance',
          value: formatMoney(cashBalance),
          highlight: 'positive',
        },
        {
          label: 'Equities Ratio',
          value: totalValue > 0 ? `${((equityVal / totalValue) * 100).toFixed(1)}%` : '0%',
        },
        {
          label: 'Cash Ratio',
          value: totalValue > 0 ? `${((cashBalance / totalValue) * 100).toFixed(1)}%` : '0%',
        },
      )
      footer = 'Formula: Total Net Worth = Market Value of Stocks + Available USD Cash'
    } else if (type === 'cash') {
      title = 'Available Cash (USD)'
      subtitle = 'Trading & Withdrawal Balance'
      metrics.push(
        {
          label: 'Cash Balance',
          value: formatMoney(cashBalance),
          highlight: 'positive',
        },
        {
          label: 'Status',
          value: 'Immediately Available',
          highlight: 'accent',
        },
      )
      footer = 'Uninvested cash ready for placing buy orders or withdrawing'
    } else if (type === 'cost') {
      title = 'Total Cost Basis'
      subtitle = 'Total Invested Capital'
      metrics.push(
        {
          label: 'Original Capital',
          value: formatMoney(stockCostBasis),
          highlight: 'neutral',
        },
        {
          label: 'Holdings Count',
          value: `${stockCount} Holdings`,
        },
      )
      footer = 'Total cumulative capital deployed into currently held stock positions'
    } else if (type === 'pnl') {
      title = 'Unrealized Profit & Loss'
      subtitle = 'Paper Gain / Loss'
      metrics.push(
        {
          label: 'Net P&L',
          value: `${formatMoney(totalPnL)} (${formatPercent(totalPnLPercent)})`,
          highlight: totalPnL >= 0 ? 'positive' : 'negative',
        },
        {
          label: 'Winning Positions',
          value: `${gainersCount} Positions`,
          highlight: 'positive',
        },
        {
          label: 'Losing Positions',
          value: `${losersCount} Positions`,
          highlight: 'negative',
        },
      )
      footer = 'Calculated based on real-time market prices versus average acquisition cost'
    }

    setFloatingTooltip({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      title,
      subtitle,
      color: '#3be3ff',
      metrics,
      footer,
    })
  }

  const handleMouseMoveTooltip = (e: React.MouseEvent) => {
    setFloatingTooltip((prev) => (prev.visible ? { ...prev, x: e.clientX, y: e.clientY } : prev))
  }

  const handleHideTooltip = () => {
    setFloatingTooltip((prev) => ({ ...prev, visible: false }))
  }

  const handleDepositSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const amount = parseFloat(depositAmount)
    if (!amount || amount <= 0 || Number.isNaN(amount)) {
      setDepositStatus({ type: 'error', message: 'Please enter a valid deposit amount greater than 0.' })
      return
    }

    setDepositing(true)
    setDepositStatus(null)

    try {
      const res = await topupAsset(amount)
      setCashBalance(res.new_cash_balance)
      setDepositStatus({
        type: 'success',
        message:
          res.message ||
          `Successfully deposited ${formatMoney(amount)}! New balance: ${formatMoney(res.new_cash_balance)}`,
      })
      await loadPortfolio()
      setTimeout(() => {
        setIsDepositOpen(false)
        setDepositStatus(null)
      }, 1500)
    } catch (err) {
      console.error('Failed to top up funds:', err)
      const msg = err instanceof Error ? err.message : 'Deposit failed. Please try again.'
      setDepositStatus({ type: 'error', message: msg })
    } finally {
      setDepositing(false)
    }
  }

  return (
    <AppLayout>
      <div className="portfolio-page">
        {/* Header Bar */}
        <header className="portfolio-header">
          <div>
            <div className="portfolio-kicker-row">
              <span className="portfolio-kicker">Investment Overview</span>
              <span className="portfolio-live-badge">
                <span className="pulse-dot" /> LIVE FEED
              </span>
            </div>
            <h1>My Portfolio</h1>
          </div>

          <div className="portfolio-actions">
            <button
              type="button"
              className="portfolio-btn-deposit"
              onClick={() => {
                setIsDepositOpen(true)
                setDepositStatus(null)
              }}
            >
              + Deposit Funds
            </button>
            <button
              type="button"
              className="portfolio-btn-refresh"
              onClick={loadPortfolio}
              disabled={loading}
              title="Refresh portfolio holdings"
            >
              {loading ? 'Refreshing...' : '↻ Refresh'}
            </button>
            <Link to="/trading" className="portfolio-btn-trade-link">
              + New Trade
            </Link>
          </div>
        </header>

        {error && (
          <div className="portfolio-notice error">
            <span>{error}. If you just registered or have no holdings yet, deposit funds and execute your first trade.</span>
            <button type="button" className="btn-holding-trade" onClick={loadPortfolio}>
              Retry
            </button>
          </div>
        )}

        {/* ─── Metric Cards Grid ──────────────────────────────────────────────── */}
        <section className="portfolio-summary-grid" aria-label="Portfolio summary">
          {/* Card 1: Total Portfolio Value */}
          <div
            className="portfolio-summary-card"
            onMouseEnter={(e) => handleShowSummaryTooltip(e, 'networth')}
            onMouseMove={handleMouseMoveTooltip}
            onMouseLeave={handleHideTooltip}
          >
            <div className="summary-card-header-row">
              <p className="summary-card-title">Total Portfolio Value</p>
              <span className="summary-info-trigger" title="View calculation details">ℹ</span>
            </div>
            <p className="summary-card-value">{formatMoney(totalValue)}</p>
            <div className="summary-card-footer-row">
              <span className="summary-card-change neutral">
                {stockCount} Stock Holding{stockCount === 1 ? '' : 's'} • {formatMoney(totalValue - cashBalance)}
              </span>
            </div>
          </div>

          {/* Card 2: Available Cash */}
          <div
            className="portfolio-summary-card"
            onMouseEnter={(e) => handleShowSummaryTooltip(e, 'cash')}
            onMouseMove={handleMouseMoveTooltip}
            onMouseLeave={handleHideTooltip}
          >
            <div className="summary-card-header-row">
              <p className="summary-card-title">Available Cash (USD)</p>
              <span className="summary-info-trigger" title="View details">ℹ</span>
            </div>
            <p className="summary-card-value" style={{ color: '#53e6b7' }}>
              {formatMoney(cashBalance)}
            </p>
            <div className="summary-card-footer-row">
              <button
                type="button"
                className="summary-deposit-action-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  setIsDepositOpen(true)
                  setDepositStatus(null)
                }}
              >
                + Deposit
              </button>
            </div>
          </div>

          {/* Card 3: Total Cost Basis */}
          <div
            className="portfolio-summary-card"
            onMouseEnter={(e) => handleShowSummaryTooltip(e, 'cost')}
            onMouseMove={handleMouseMoveTooltip}
            onMouseLeave={handleHideTooltip}
          >
            <div className="summary-card-header-row">
              <p className="summary-card-title">Total Cost Basis</p>
              <span className="summary-info-trigger" title="View details">ℹ</span>
            </div>
            <p className="summary-card-value">{formatMoney(stockCostBasis)}</p>
            <div className="summary-card-footer-row">
              <span className="summary-card-change neutral">Total invested in stocks</span>
            </div>
          </div>

          {/* Card 4: Unrealized P&L */}
          <div
            className="portfolio-summary-card"
            onMouseEnter={(e) => handleShowSummaryTooltip(e, 'pnl')}
            onMouseMove={handleMouseMoveTooltip}
            onMouseLeave={handleHideTooltip}
          >
            <div className="summary-card-header-row">
              <p className="summary-card-title">Unrealized P&L</p>
              <span className="summary-info-trigger" title="View details">ℹ</span>
            </div>
            <p className={`summary-card-value ${pnlClass}`}>{formatMoney(totalPnL)}</p>
            <div className="summary-card-footer-row">
              <span className={`summary-card-change ${pnlClass}`}>
                {formatPercent(totalPnLPercent)}
              </span>
              {stockCount > 0 && (
                <span className="summary-sub-stat">
                  ({gainersCount} Gain • {losersCount} Loss)
                </span>
              )}
            </div>
          </div>
        </section>

        {/* ─── Interactive Charts Section ────────────────────────────────────── */}
        {totalValue > 0 && (
          <PortfolioCharts
            holdings={enrichedHoldings}
            cashBalance={cashBalance}
            totalValue={totalValue}
            onSelectSymbol={(sym) => {
              setSelectedSymbol((prev) => (prev === sym ? null : sym))
            }}
          />
        )}

        {/* ─── Holdings Table Section ────────────────────────────────────────── */}
        <section className="portfolio-table-section">
          {/* Table Controls: Search, Filter Tabs, Sort Dropdown */}
          <div className="portfolio-controls-bar">
            <div className="portfolio-controls-left">
              <div className="portfolio-search-box">
                <span className="search-icon">🔍</span>
                <input
                  type="text"
                  placeholder="Search symbol or company name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="portfolio-search-input"
                />
                {searchQuery && (
                  <button
                    type="button"
                    className="portfolio-search-clear"
                    onClick={() => setSearchQuery('')}
                    aria-label="Clear search"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Status Filter Chips */}
              <div className="portfolio-filter-chips">
                <button
                  type="button"
                  className={`filter-chip ${filterStatus === 'all' && !selectedSymbol ? 'active' : ''}`}
                  onClick={() => {
                    setFilterStatus('all')
                    setSelectedSymbol(null)
                  }}
                >
                  All ({enrichedHoldings.length})
                </button>
                <button
                  type="button"
                  className={`filter-chip ${filterStatus === 'gainers' ? 'active' : ''}`}
                  onClick={() => {
                    setFilterStatus('gainers')
                    setSelectedSymbol(null)
                  }}
                >
                  Gainers ({gainersCount})
                </button>
                <button
                  type="button"
                  className={`filter-chip ${filterStatus === 'losers' ? 'active' : ''}`}
                  onClick={() => {
                    setFilterStatus('losers')
                    setSelectedSymbol(null)
                  }}
                >
                  Losers ({losersCount})
                </button>

                {selectedSymbol && (
                  <button
                    type="button"
                    className="filter-chip selected-symbol-chip"
                    onClick={() => setSelectedSymbol(null)}
                    title="Clear chart filter"
                  >
                    Filtered: <strong>{selectedSymbol}</strong> ✕
                  </button>
                )}
              </div>
            </div>

            {/* Sort Dropdown */}
            <div className="portfolio-controls-right">
              <label htmlFor="portfolio-sort" className="sort-label">
                Sort by:
              </label>
              <select
                id="portfolio-sort"
                className="portfolio-sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortBy)}
              >
                <option value="value_desc">Highest Market Value</option>
                <option value="pnl_desc">Highest Return (%)</option>
                <option value="pnl_asc">Lowest Return (%)</option>
                <option value="symbol_asc">Symbol (A-Z)</option>
              </select>
            </div>
          </div>

          {/* Table Container */}
          <div className="portfolio-table-container">
            {loading && enrichedHoldings.length === 0 ? (
              <div className="portfolio-empty-state">
                <div className="portfolio-empty-spinner" />
                <p>Loading your portfolio holdings...</p>
              </div>
            ) : enrichedHoldings.length === 0 ? (
              <div className="portfolio-empty-state">
                <div className="portfolio-empty-icon">📊</div>
                <h3>No Stock Holdings Yet</h3>
                <p>
                  {cashBalance > 0
                    ? `You have ${formatMoney(cashBalance)} in available cash. Explore symbols and place your first trade!`
                    : 'Deposit funds or explore symbols to start building your portfolio.'}
                </p>
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                  <button
                    type="button"
                    className="portfolio-btn-deposit"
                    onClick={() => setIsDepositOpen(true)}
                  >
                    + Deposit Funds
                  </button>
                  <Link to="/trading" className="portfolio-btn-trade-link">
                    Start Trading →
                  </Link>
                </div>
              </div>
            ) : displayedHoldings.length === 0 ? (
              <div className="portfolio-empty-state">
                <div className="portfolio-empty-icon">🔍</div>
                <h3>No matching symbols found</h3>
                <p>Try adjusting your search query or switching filters.</p>
                <button
                  type="button"
                  className="btn-holding-trade"
                  onClick={() => {
                    setSearchQuery('')
                    setFilterStatus('all')
                    setSelectedSymbol(null)
                  }}
                >
                  Clear Filters
                </button>
              </div>
            ) : (
              <table className="portfolio-table">
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Weight</th>
                    <th>Quantity</th>
                    <th>Avg Cost</th>
                    <th>Current Price</th>
                    <th>Market Value</th>
                    <th>Unrealized P&L</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedHoldings.map((h) => {
                    const holdingPnlClass =
                      h.livePnL > 0 ? 'positive' : h.livePnL < 0 ? 'negative' : 'neutral'
                    const weight = totalValue > 0 ? (h.marketValue / totalValue) * 100 : 0

                    return (
                      <tr
                        key={h.symbol}
                        className={selectedSymbol === h.symbol ? 'row-selected' : ''}
                      >
                        {/* 1. Asset Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h, 'ticker')}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <div className="holding-ticker-cell">
                            <div className="holding-avatar">
                              {h.logo ? (
                                <img
                                  src={h.logo}
                                  alt={h.symbol}
                                  className="holding-logo-img"
                                  onError={(e) => {
                                    ;(e.target as HTMLElement).style.display = 'none'
                                  }}
                                />
                              ) : null}
                              <span>{h.symbol.slice(0, 2)}</span>
                            </div>
                            <div className="holding-name-box">
                              <Link
                                to={`/stock/${encodeURIComponent(h.symbol)}`}
                                className="holding-ticker-link"
                              >
                                {h.symbol}
                              </Link>
                              {h.name && (
                                <span className="holding-company-name" title={h.name}>
                                  {h.name}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* 2. Weight % Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h, 'weight')}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <div className="holding-weight-box">
                            <div className="holding-weight-bar">
                              <div
                                className="holding-weight-fill"
                                style={{ width: `${Math.min(100, Math.max(2, weight))}%` }}
                              />
                            </div>
                            <span className="holding-weight-text">{weight.toFixed(1)}%</span>
                          </div>
                        </td>

                        {/* 3. Quantity Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h)}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <span className="holding-qty-text">{h.quantity.toLocaleString()}</span>
                        </td>

                        {/* 4. Avg Cost Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h, 'cost')}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <span className="holding-cost-text">{formatMoney(h.price)}</span>
                        </td>

                        {/* 5. Current Price Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h, 'price')}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <span className="holding-price-text">{formatMoney(h.currentPrice)}</span>
                        </td>

                        {/* 6. Market Value Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h)}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <strong className="holding-market-value">{formatMoney(h.marketValue)}</strong>
                        </td>

                        {/* 7. Unrealized P&L Cell */}
                        <td
                          onMouseEnter={(e) => handleShowTableTooltip(e, h, 'pnl')}
                          onMouseMove={handleMouseMoveTooltip}
                          onMouseLeave={handleHideTooltip}
                        >
                          <div className={`holding-pnl-badge ${holdingPnlClass}`}>
                            <span>{formatMoney(h.livePnL)}</span>
                            <span className="holding-pnl-sub">({formatPercent(h.livePnLPercent)})</span>
                          </div>
                        </td>

                        {/* 8. Actions Cell */}
                        <td>
                          <div className="holding-actions" style={{ justifyContent: 'flex-end' }}>
                            <Link
                              to={`/trading?symbol=${encodeURIComponent(h.symbol)}&operation=BUY`}
                              className="btn-holding-trade"
                              title={`Buy more ${h.symbol}`}
                            >
                              Buy
                            </Link>
                            <Link
                              to={`/trading?symbol=${encodeURIComponent(h.symbol)}&operation=SELL`}
                              className="btn-holding-trade btn-holding-sell"
                              title={`Sell ${h.symbol}`}
                            >
                              Sell
                            </Link>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Global Floating Tooltip for Table & Summary Cards */}
        <PortfolioTooltip {...floatingTooltip} />
      </div>

      {/* Deposit Modal */}
      {isDepositOpen && (
        <div
          className="deposit-modal-backdrop"
          onClick={() => !depositing && setIsDepositOpen(false)}
        >
          <div className="deposit-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="deposit-modal-header">
              <h3 className="deposit-modal-title">
                <span>💵</span> Deposit Funds (USD)
              </h3>
              <button
                type="button"
                className="deposit-modal-close"
                onClick={() => !depositing && setIsDepositOpen(false)}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            <div className="deposit-balance-box">
              <div>
                <p className="deposit-balance-label">Current Cash Balance</p>
                <p className="deposit-balance-value">{formatMoney(cashBalance)}</p>
              </div>
              <span style={{ fontSize: '26px' }}>🏦</span>
            </div>

            <form onSubmit={handleDepositSubmit} className="deposit-form">
              <div className="deposit-field-group">
                <label className="deposit-field-label" htmlFor="deposit-amount">
                  Deposit Amount (USD)
                </label>
                <div className="deposit-input-wrapper">
                  <span className="deposit-currency-symbol">$</span>
                  <input
                    id="deposit-amount"
                    type="number"
                    className="deposit-amount-input"
                    min="1"
                    step="any"
                    placeholder="1,000"
                    value={depositAmount}
                    onChange={(e) => setDepositAmount(e.target.value)}
                    disabled={depositing}
                    autoFocus
                    required
                  />
                </div>
              </div>

              <div>
                <p className="deposit-presets-label">Quick Select</p>
                <div className="deposit-presets-grid">
                  {[100, 500, 1000, 5000, 10000].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      className={`deposit-preset-btn ${depositAmount === String(preset) ? 'active' : ''}`}
                      onClick={() => setDepositAmount(String(preset))}
                      disabled={depositing}
                    >
                      +${preset.toLocaleString()}
                    </button>
                  ))}
                </div>
              </div>

              {depositStatus && (
                <div className={`deposit-alert ${depositStatus.type}`}>
                  <span>{depositStatus.type === 'success' ? '✓' : '⚠'}</span>
                  <span>{depositStatus.message}</span>
                </div>
              )}

              <div className="deposit-modal-actions">
                <button
                  type="button"
                  className="deposit-btn-cancel"
                  onClick={() => setIsDepositOpen(false)}
                  disabled={depositing}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="deposit-btn-submit"
                  disabled={depositing || !depositAmount || Number(depositAmount) <= 0}
                >
                  {depositing
                    ? 'Processing...'
                    : `Deposit ${Number(depositAmount) > 0 ? formatMoney(Number(depositAmount)) : ''}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  )
}
