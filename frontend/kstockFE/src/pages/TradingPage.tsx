import { useEffect, useState, useCallback, useMemo } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import { submitOrder, getTransactionHistory } from '../services/transaction.service'
import { getSymbols } from '../services/symbol.service'
import { getCashBalance } from '../services/asset.service'
import type {
  BuyOrderResponse,
  OrderOperation,
  SellOrderResponse,
  SymbolPreview,
  TransactionHistoryItem,
} from '../types'
import { useLivePrices } from '../context'
import './TradingPage.css'

function formatMoney(value: number): string {
  if (!Number.isFinite(value)) return '$0.00'
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function TradingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSymbol = (searchParams.get('symbol') || 'AAPL').toUpperCase()
  const urlOp = searchParams.get('operation')?.toUpperCase() === 'SELL' ? 'SELL' : 'BUY'

  const [symbol, setSymbol] = useState(urlSymbol)
  const [operation, setOperation] = useState<OrderOperation>(urlOp)
  const [quantity, setQuantity] = useState<number>(1)
  const [allSymbols, setAllSymbols] = useState<SymbolPreview[]>([])
  const [cashBalance, setCashBalance] = useState<number | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [orderError, setOrderError] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<BuyOrderResponse | SellOrderResponse | null>(null)

  // Transaction history state
  const [history, setHistory] = useState<TransactionHistoryItem[]>([])
  const [page, setPage] = useState<number>(1)
  const [totalPages, setTotalPages] = useState<number>(1)
  const [totalRecords, setTotalRecords] = useState<number>(0)
  const [historyLoading, setHistoryLoading] = useState<boolean>(false)
  const [historyFilter, setHistoryFilter] = useState<string>('')

  // Live prices hook
  const { prices } = useLivePrices(symbol ? [symbol] : [])

  // Load available cash balance independently
  useEffect(() => {
    let isMounted = true
    getCashBalance()
      .then((res) => {
        if (isMounted) setCashBalance(res.cash_balance)
      })
      .catch((err) => console.warn('Could not load cash balance:', err))
    return () => {
      isMounted = false
    }
  }, [])

  // Load symbol catalog for autocomplete
  useEffect(() => {
    let isMounted = true
    getSymbols({ exchange: 'NASDAQ', order_by: 'name' })
      .then((res) => {
        if (isMounted) setAllSymbols(res.data ?? [])
      })
      .catch((err) => console.warn('Could not load symbols for suggestion:', err))
    return () => {
      isMounted = false
    }
  }, [])

  // Fetch paginated transaction history
  useEffect(() => {
    let isMounted = true

    async function fetchHistory() {
      if (isMounted) setHistoryLoading(true)
      try {
        const res = await getTransactionHistory(page)
        if (isMounted) {
          setHistory(res.data ?? [])
          setTotalPages(res.total_pages || 1)
          setTotalRecords(res.total || (res.data ?? []).length)
          setHistoryLoading(false)
        }
      } catch (err) {
        console.warn('Could not load transaction history:', err)
        if (isMounted) setHistoryLoading(false)
      }
    }

    fetchHistory()
    return () => {
      isMounted = false
    }
  }, [page])

  const reloadHistory = useCallback(async (targetPage: number) => {
    setHistoryLoading(true)
    try {
      const res = await getTransactionHistory(targetPage)
      setHistory(res.data ?? [])
      setPage(res.page)
      setTotalPages(res.total_pages || 1)
      setTotalRecords(res.total || (res.data ?? []).length)
    } catch (err) {
      console.warn('Could not reload history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  // Resolve active symbol price from live feed or symbol catalog
  const currentPrice = useMemo(() => {
    const live = prices[symbol.toUpperCase()]
    if (live && live.price > 0) return live.price
    const match = allSymbols.find((s) => s.ticker.toUpperCase() === symbol.toUpperCase())
    return match?.lastPrice || 0
  }, [prices, symbol, allSymbols])

  const estimatedTotal = (quantity > 0 ? quantity : 0) * currentPrice

  const handleSymbolChange = (newSym: string) => {
    const upper = newSym.toUpperCase()
    setSymbol(upper)
    setSearchParams({ symbol: upper, operation })
  }

  const handleOpChange = (newOp: OrderOperation) => {
    setOperation(newOp)
    setSearchParams({ symbol, operation: newOp })
  }

  const handleSubmitOrder = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setOrderError(null)

    if (!symbol.trim()) {
      setOrderError('Please specify a stock symbol.')
      return
    }

    if (!quantity || quantity <= 0 || !Number.isInteger(Number(quantity))) {
      setOrderError('Quantity must be a positive integer.')
      return
    }

    setSubmitting(true)
    try {
      const result = await submitOrder({
        symbol: symbol.trim().toUpperCase(),
        quantity: Number(quantity),
        operation,
      })
      setLastResult(result)
      if ('new_cash_balance' in result && typeof result.new_cash_balance === 'number') {
        setCashBalance(result.new_cash_balance)
      }
      // Refresh transaction history
      reloadHistory(1)
    } catch (err) {
      console.error('Order failed:', err)
      setOrderError(err instanceof Error ? err.message : 'Order submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const isInsufficientCash =
    operation === 'BUY' &&
    cashBalance !== null &&
    currentPrice > 0 &&
    estimatedTotal > cashBalance

  const filteredHistory = useMemo(() => {
    const filter = historyFilter.trim().toUpperCase()
    if (!filter) return history
    return history.filter((item) => item.symbol.toUpperCase().includes(filter))
  }, [history, historyFilter])

  return (
    <AppLayout>
      <div className="trading-page">
        <header className="trading-header">
          <p className="trading-kicker">Execution Desk</p>
          <h1>Trade Equities</h1>
        </header>

        <div className="trading-grid">
          {/* Order Placement Form */}
          <div className="trading-card">
            <h2 className="trading-card-title">Place Order</h2>

            <div className="order-op-toggle">
              <button
                type="button"
                className={`order-op-btn buy ${operation === 'BUY' ? 'active' : ''}`}
                onClick={() => handleOpChange('BUY')}
              >
                BUY
              </button>
              <button
                type="button"
                className={`order-op-btn sell ${operation === 'SELL' ? 'active' : ''}`}
                onClick={() => handleOpChange('SELL')}
              >
                SELL
              </button>
            </div>

            {orderError && (
              <div style={{ padding: '10px 14px', background: 'rgba(239, 83, 80, 0.15)', border: '1px solid rgba(239, 83, 80, 0.4)', borderRadius: '8px', color: '#ff8a9a', fontSize: '13px', marginBottom: '14px' }}>
                {orderError}
              </div>
            )}

            <form className="order-form" onSubmit={handleSubmitOrder}>
              <label className="order-field">
                <span>Symbol</span>
                <input
                  type="text"
                  list="symbol-suggestions"
                  value={symbol}
                  onChange={(e) => handleSymbolChange(e.target.value)}
                  placeholder="e.g. AAPL, MSFT, TSLA"
                  required
                />
                <datalist id="symbol-suggestions">
                  {allSymbols.map((s) => (
                    <option key={s.ticker} value={s.ticker}>
                      {s.name}
                    </option>
                  ))}
                </datalist>
              </label>

              <label className="order-field">
                <span>Quantity (Shares)</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  required
                />
              </label>

              <div className="order-preview">
                <div className="order-preview-row">
                  <span>Available Cash:</span>
                  <strong style={{ color: '#53e6b7' }}>
                    {cashBalance !== null ? formatMoney(cashBalance) : 'Loading...'}
                  </strong>
                </div>
                <div className="order-preview-row">
                  <span>Estimated Unit Price:</span>
                  <strong>{currentPrice > 0 ? formatMoney(currentPrice) : 'Market rate'}</strong>
                </div>
                <div className="order-preview-row">
                  <span>Estimated {operation === 'BUY' ? 'Cost' : 'Proceeds'}:</span>
                  <strong style={{ color: isInsufficientCash ? '#ff8a9a' : '#f4f7ff' }}>
                    {currentPrice > 0 ? formatMoney(estimatedTotal) : '--'}
                  </strong>
                </div>
              </div>

              {isInsufficientCash && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: 'rgba(239, 83, 80, 0.14)',
                    border: '1px solid rgba(239, 83, 80, 0.35)',
                    color: '#ff9da8',
                    fontSize: '13px',
                    marginTop: '10px',
                  }}
                >
                  <span>
                    Insufficient cash balance (short by{' '}
                    {formatMoney(estimatedTotal - (cashBalance || 0))})
                  </span>
                  <Link
                    to="/portfolio"
                    style={{
                      color: '#3be3ff',
                      fontWeight: 700,
                      textDecoration: 'none',
                      whiteSpace: 'nowrap',
                      marginLeft: '8px',
                    }}
                  >
                    + Deposit
                  </Link>
                </div>
              )}

              <button
                type="submit"
                className={`order-submit-btn ${operation.toLowerCase()}`}
                disabled={submitting || !symbol.trim() || isInsufficientCash}
              >
                {submitting
                  ? 'Submitting order...'
                  : `${operation} ${quantity} ${symbol || 'Shares'}`}
              </button>
            </form>
          </div>

          {/* Execution Summary & Market Status */}
          <div>
            {lastResult ? (
              <div className="trading-result-card">
                <div className="result-badge success">
                  ✓ {lastResult.message || `${operation} Order Executed`}
                </div>

                <div className="result-stat-grid">
                  <div className="result-stat-box">
                    <div className="result-stat-label">Symbol</div>
                    <div className="result-stat-val">
                      <Link to={`/stock/${encodeURIComponent(lastResult.symbol)}`} style={{ color: '#3be3ff' }}>
                        {lastResult.symbol}
                      </Link>
                    </div>
                  </div>

                  <div className="result-stat-box">
                    <div className="result-stat-label">Quantity</div>
                    <div className="result-stat-val">{lastResult.amount.toLocaleString()}</div>
                  </div>

                  <div className="result-stat-box">
                    <div className="result-stat-label">Execution Price</div>
                    <div className="result-stat-val">{formatMoney(lastResult.price)}</div>
                  </div>

                  {'total_cost' in lastResult && (
                    <div className="result-stat-box">
                      <div className="result-stat-label">Total Cost</div>
                      <div className="result-stat-val">{formatMoney(lastResult.total_cost)}</div>
                    </div>
                  )}

                  {'total_proceeds' in lastResult && (
                    <div className="result-stat-box">
                      <div className="result-stat-label">Total Proceeds</div>
                      <div className="result-stat-val">
                        {typeof lastResult.total_proceeds === 'number'
                          ? formatMoney(lastResult.total_proceeds)
                          : String(lastResult.total_proceeds)}
                      </div>
                    </div>
                  )}

                  {'new_cash_balance' in lastResult && (
                    <div className="result-stat-box">
                      <div className="result-stat-label">New Cash Balance</div>
                      <div className="result-stat-val">
                        {typeof lastResult.new_cash_balance === 'number'
                          ? formatMoney(lastResult.new_cash_balance)
                          : String(lastResult.new_cash_balance)}
                      </div>
                    </div>
                  )}

                  {'total_holdings' in lastResult && (
                    <div className="result-stat-box">
                      <div className="result-stat-label">Total Holdings</div>
                      <div className="result-stat-val">{lastResult.total_holdings.toLocaleString()}</div>
                    </div>
                  )}

                  {'remaining_holdings' in lastResult && (
                    <div className="result-stat-box">
                      <div className="result-stat-label">Remaining Holdings</div>
                      <div className="result-stat-val">{String(lastResult.remaining_holdings)}</div>
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '12px', marginTop: '6px' }}>
                  <Link to="/portfolio" className="btn-holding-trade" style={{ padding: '8px 14px' }}>
                    View in Portfolio
                  </Link>
                  <button
                    type="button"
                    className="btn-holding-trade"
                    style={{ padding: '8px 14px' }}
                    onClick={() => setLastResult(null)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ) : (
              <div className="trading-card" style={{ height: '100%', boxSizing: 'border-box' }}>
                <h2 className="trading-card-title">Order Information</h2>
                <p style={{ color: '#abb5cb', fontSize: '14px', lineHeight: 1.6, margin: '0 0 16px' }}>
                  Orders are executed instantly against the backend matching engine at the current market price.
                </p>
                <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(10, 14, 26, 0.7)', border: '1px solid rgba(255, 255, 255, 0.06)', display: 'grid', gap: '10px', fontSize: '13px', color: '#abb5cb' }}>
                  <div>• <strong>BUY Orders</strong> deduct the total cost from your cash balance and credit holdings.</div>
                  <div>• <strong>SELL Orders</strong> deduct shares from your portfolio and credit cash proceeds.</div>
                  <div>• Prices are updated in real-time via live market feeds.</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Paginated Transaction History */}
        <section className="tx-history-section" aria-label="Transaction history">
          <div className="tx-history-header">
            <h2>Transaction History ({totalRecords})</h2>
            <input
              type="search"
              className="tx-search-input"
              placeholder="Filter by symbol..."
              value={historyFilter}
              onChange={(e) => setHistoryFilter(e.target.value)}
            />
          </div>

          <div className="tx-table-wrapper">
            {historyLoading ? (
              <p style={{ textAlign: 'center', color: '#abb5cb', padding: '30px 0' }}>
                Loading transaction history...
              </p>
            ) : filteredHistory.length === 0 ? (
              <p style={{ textAlign: 'center', color: '#abb5cb', padding: '30px 0' }}>
                No transaction records found.
              </p>
            ) : (
              <table className="tx-table">
                <thead>
                  <tr>
                    <th>Date & Time</th>
                    <th>Type</th>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Total Value</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map((tx) => {
                    const isBuy = tx.operation.toUpperCase() === 'BUY'
                    const totalVal = tx.amount * tx.price
                    return (
                      <tr key={tx.id || `${tx.symbol}-${tx.time_transacted}`}>
                        <td>{formatDate(tx.time_transacted)}</td>
                        <td>
                          <span className={`tx-badge ${isBuy ? 'buy' : 'sell'}`}>
                            {tx.operation.toUpperCase()}
                          </span>
                        </td>
                        <td>
                          <Link
                            to={`/stock/${encodeURIComponent(tx.symbol)}`}
                            style={{ color: '#edf2ff', fontWeight: 600, textDecoration: 'none' }}
                          >
                            {tx.symbol}
                          </Link>
                        </td>
                        <td>{tx.amount.toLocaleString()}</td>
                        <td>{formatMoney(tx.price)}</td>
                        <td>
                          <strong>{formatMoney(totalVal)}</strong>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>

          {totalPages > 1 && (
            <div className="tx-pagination">
              <button
                type="button"
                disabled={page <= 1 || historyLoading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages || historyLoading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          )}
        </section>
      </div>
    </AppLayout>
  )
}
