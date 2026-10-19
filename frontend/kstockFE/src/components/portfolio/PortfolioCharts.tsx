import React, { useState, useMemo, useCallback } from 'react'
import PortfolioTooltip, { type TooltipMetric } from './PortfolioTooltip'
import './PortfolioCharts.css'

export interface EnrichedHolding {
  symbol: string
  name?: string
  logo?: string
  quantity: number
  price: number // average buy price
  currentPrice: number // current market price
  marketValue: number
  costBasis: number
  livePnL: number
  livePnLPercent: number
}

export interface PortfolioChartsProps {
  holdings: EnrichedHolding[]
  cashBalance: number
  totalValue: number
  onSelectSymbol?: (symbol: string) => void
}

const PALETTE = [
  '#7c5cff', // Neon Purple
  '#3be3ff', // Neon Cyan
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#8b5cf6', // Violet
  '#06b6d4', // Teal
  '#eab308', // Yellow
  '#f97316', // Orange
  '#a855f7', // Purple
  '#14b8a6', // Mint Teal
]

const CASH_COLOR = '#10b981' // Emerald Green for Cash

function formatCurrency(val: number): string {
  if (!Number.isFinite(val)) return '$0.00'
  return `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPercent(val: number): string {
  if (!Number.isFinite(val)) return '0.00%'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

interface AllocationSlice {
  id: string
  symbol: string
  name: string
  value: number
  weightPercent: number
  color: string
  isCash: boolean
  holding?: EnrichedHolding
  startAngle: number
  endAngle: number
  pathD: string
  hoverTransform: string
}

export const PortfolioCharts: React.FC<PortfolioChartsProps> = ({
  holdings,
  cashBalance,
  totalValue,
  onSelectSymbol,
}) => {
  const [activeTab, setActiveTab] = useState<'allocation' | 'performance'>('allocation')
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [tooltipData, setTooltipData] = useState<{
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

  // Slices configuration for Donut Chart
  const slices = useMemo(() => {
    if (totalValue <= 0) return []

    const items: Array<{
      id: string
      symbol: string
      name: string
      value: number
      color: string
      isCash: boolean
      holding?: EnrichedHolding
    }> = []

    // 1. Stock holdings (sorted by market value descending)
    const sortedHoldings = [...holdings].sort((a, b) => b.marketValue - a.marketValue)
    sortedHoldings.forEach((h, index) => {
      if (h.marketValue > 0) {
        items.push({
          id: h.symbol,
          symbol: h.symbol,
          name: h.name || h.symbol,
          value: h.marketValue,
          color: PALETTE[index % PALETTE.length],
          isCash: false,
          holding: h,
        })
      }
    })

    // 2. Cash balance
    if (cashBalance > 0) {
      items.push({
        id: 'USD_CASH',
        symbol: 'USD Cash',
        name: 'Available Cash',
        value: cashBalance,
        color: CASH_COLOR,
        isCash: true,
      })
    }

    if (items.length === 0) return []

    // Geometry parameters
    const cx = 140
    const cy = 140
    const outerR = 112
    const innerR = 72
    const padAngle = items.length > 1 ? 0.02 : 0 // Small gap between slices

    let currentAngle = 0
    const totalItemsValue = items.reduce((sum, item) => sum + item.value, 0)

    return items.map((item) => {
      const weightPercent = (item.value / totalItemsValue) * 100
      const sliceAngle = (item.value / totalItemsValue) * (Math.PI * 2)

      const start = currentAngle + padAngle / 2
      const end = currentAngle + sliceAngle - padAngle / 2
      currentAngle += sliceAngle

      // Arc trigonometry (offset -PI/2 so 0 is at 12 o'clock)
      const a0 = start - Math.PI / 2
      const a1 = end - Math.PI / 2
      const largeArc = sliceAngle > Math.PI ? 1 : 0

      const x0 = cx + outerR * Math.cos(a0)
      const y0 = cy + outerR * Math.sin(a0)
      const x1 = cx + outerR * Math.cos(a1)
      const y1 = cy + outerR * Math.sin(a1)
      const x2 = cx + innerR * Math.cos(a1)
      const y2 = cy + innerR * Math.sin(a1)
      const x3 = cx + innerR * Math.cos(a0)
      const y3 = cy + innerR * Math.sin(a0)

      // Hover displacement along bisector angle
      const midAngle = (a0 + a1) / 2
      const hoverDx = Math.cos(midAngle) * 7
      const hoverDy = Math.sin(midAngle) * 7

      const pathD = `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${outerR} ${outerR} 0 ${largeArc} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} L ${x2.toFixed(2)} ${y2.toFixed(2)} A ${innerR} ${innerR} 0 ${largeArc} 0 ${x3.toFixed(2)} ${y3.toFixed(2)} Z`

      return {
        ...item,
        weightPercent,
        startAngle: start,
        endAngle: end,
        pathD,
        hoverTransform: `translate(${hoverDx.toFixed(1)}px, ${hoverDy.toFixed(1)}px)`,
      } as AllocationSlice
    })
  }, [holdings, cashBalance, totalValue])

  // Center display item for Donut Chart
  const centerItem = useMemo(() => {
    if (!hoveredId) return null
    return slices.find((s) => s.id === hoveredId) ?? null
  }, [hoveredId, slices])

  // Handle tooltip display
  const showTooltip = useCallback(
    (e: React.MouseEvent, slice: AllocationSlice) => {
      setHoveredId(slice.id)
      const metrics: TooltipMetric[] = [
        {
          label: 'Market Value',
          value: formatCurrency(slice.value),
          highlight: 'accent',
        },
        {
          label: 'Portfolio Weight',
          value: `${slice.weightPercent.toFixed(1)}%`,
          highlight: slice.isCash ? 'cash' : 'accent',
        },
      ]

      if (slice.holding) {
        const h = slice.holding
        metrics.push(
          {
            label: 'Shares Held',
            value: `${h.quantity.toLocaleString()} Shares`,
          },
          {
            label: 'Avg Cost Basis',
            value: formatCurrency(h.price),
          },
          {
            label: 'Current Price',
            value: formatCurrency(h.currentPrice),
          },
          {
            label: 'Cost Basis',
            value: formatCurrency(h.costBasis),
          },
          {
            label: 'Unrealized P&L',
            value: `${formatCurrency(h.livePnL)} (${formatPercent(h.livePnLPercent)})`,
            highlight: h.livePnL > 0 ? 'positive' : h.livePnL < 0 ? 'negative' : 'neutral',
          },
        )
      } else if (slice.isCash) {
        metrics.push(
          {
            label: 'Status',
            value: 'Available to Trade',
            highlight: 'positive',
          },
          {
            label: 'Asset Type',
            value: 'USD Cash',
            highlight: 'neutral',
          },
        )
      }

      setTooltipData({
        visible: true,
        x: e.clientX,
        y: e.clientY,
        title: slice.symbol,
        subtitle: slice.name,
        badge: `${slice.weightPercent.toFixed(1)}% Portfolio`,
        color: slice.color,
        metrics,
        footer: slice.holding
          ? 'Hover or click to view details or place a trade'
          : 'Available cash balance for placing new trades',
      })
    },
    [],
  )

  const moveTooltip = useCallback((e: React.MouseEvent) => {
    setTooltipData((prev) => (prev.visible ? { ...prev, x: e.clientX, y: e.clientY } : prev))
  }, [])

  const hideTooltip = useCallback(() => {
    setHoveredId(null)
    setTooltipData((prev) => ({ ...prev, visible: false }))
  }, [])

  // Stats summary for header
  const equityValue = totalValue - cashBalance
  const equityRatio = totalValue > 0 ? (equityValue / totalValue) * 100 : 0
  const cashRatio = totalValue > 0 ? (cashBalance / totalValue) * 100 : 0
  const topHolding = holdings.length > 0 ? [...holdings].sort((a, b) => b.marketValue - a.marketValue)[0] : null
  const topHoldingWeight = topHolding && totalValue > 0 ? (topHolding.marketValue / totalValue) * 100 : 0

  return (
    <section className="portfolio-analytics-section" aria-label="Portfolio Analytics">
      {/* Top Bar: Tabs & Quick Ratio */}
      <div className="portfolio-analytics-header">
        <div className="portfolio-analytics-tabs">
          <button
            type="button"
            className={`analytics-tab-btn ${activeTab === 'allocation' ? 'active' : ''}`}
            onClick={() => setActiveTab('allocation')}
          >
            <span className="tab-icon">🍩</span> Asset Allocation
          </button>
          <button
            type="button"
            className={`analytics-tab-btn ${activeTab === 'performance' ? 'active' : ''}`}
            onClick={() => setActiveTab('performance')}
          >
            <span className="tab-icon">📊</span> P&L Performance
          </button>
        </div>

        {/* Mini Ratio Indicator */}
        <div className="portfolio-ratio-bar-wrapper">
          <div className="portfolio-ratio-labels">
            <span className="ratio-label-stock">
              Stocks: <strong>{equityRatio.toFixed(1)}%</strong> ({formatCurrency(equityValue)})
            </span>
            <span className="ratio-label-cash">
              Cash: <strong>{cashRatio.toFixed(1)}%</strong> ({formatCurrency(cashBalance)})
            </span>
          </div>
          <div className="portfolio-ratio-track" title="Equities vs Cash Allocation Ratio">
            <div
              className="portfolio-ratio-fill-stock"
              style={{ width: `${Math.min(100, Math.max(0, equityRatio))}%` }}
            />
            <div
              className="portfolio-ratio-fill-cash"
              style={{ width: `${Math.min(100, Math.max(0, cashRatio))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {slices.length === 0 ? (
        <div className="portfolio-analytics-empty">
          <p>No portfolio data available to generate charts.</p>
        </div>
      ) : activeTab === 'allocation' ? (
        <div className="portfolio-allocation-layout">
          {/* SVG Donut Chart */}
          <div className="portfolio-donut-container">
            <svg
              className="portfolio-donut-svg"
              viewBox="0 0 280 280"
              onMouseLeave={hideTooltip}
            >
              <defs>
                <filter id="donut-glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="6" floodOpacity="0.4" />
                </filter>
              </defs>

              {/* Background circular guide ring */}
              <circle
                cx="140"
                cy="140"
                r="92"
                fill="none"
                stroke="rgba(255, 255, 255, 0.04)"
                strokeWidth="42"
              />

              {/* Slices */}
              {slices.map((slice) => {
                const isHovered = hoveredId === slice.id
                return (
                  <path
                    key={slice.id}
                    d={slice.pathD}
                    fill={slice.color}
                    className={`donut-slice ${isHovered ? 'active' : ''}`}
                    style={{
                      transform: isHovered ? slice.hoverTransform : 'none',
                      transition: 'transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease',
                      opacity: hoveredId && !isHovered ? 0.45 : 1,
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => showTooltip(e, slice)}
                    onMouseMove={moveTooltip}
                    onMouseLeave={hideTooltip}
                    onClick={() => {
                      if (!slice.isCash && onSelectSymbol) {
                        onSelectSymbol(slice.symbol)
                      }
                    }}
                  />
                )
              })}

              {/* Center Info Text */}
              <g className="donut-center-group">
                {centerItem ? (
                  <>
                    <text
                      x="140"
                      y="122"
                      textAnchor="middle"
                      className="donut-center-title"
                      fill={centerItem.color}
                    >
                      {centerItem.symbol}
                    </text>
                    <text x="140" y="145" textAnchor="middle" className="donut-center-value">
                      {formatCurrency(centerItem.value)}
                    </text>
                    <text x="140" y="164" textAnchor="middle" className="donut-center-sub">
                      {centerItem.weightPercent.toFixed(1)}% Weight
                    </text>
                  </>
                ) : (
                  <>
                    <text x="140" y="122" textAnchor="middle" className="donut-center-title neutral">
                      NET WORTH
                    </text>
                    <text x="140" y="145" textAnchor="middle" className="donut-center-value">
                      {formatCurrency(totalValue)}
                    </text>
                    <text x="140" y="164" textAnchor="middle" className="donut-center-sub">
                      {holdings.length} Holdings • Cash {cashRatio.toFixed(0)}%
                    </text>
                  </>
                )}
              </g>
            </svg>
          </div>

          {/* Interactive Legend List */}
          <div className="portfolio-legend-container">
            <div className="portfolio-legend-header">
              <span className="legend-col-asset">Asset</span>
              <span className="legend-col-value">Value</span>
              <span className="legend-col-weight">Weight</span>
            </div>
            <div className="portfolio-legend-list">
              {slices.map((slice) => {
                const isHovered = hoveredId === slice.id
                return (
                  <div
                    key={slice.id}
                    className={`portfolio-legend-item ${isHovered ? 'active' : ''}`}
                    style={{
                      borderColor: isHovered ? `${slice.color}66` : 'transparent',
                      background: isHovered ? 'rgba(255, 255, 255, 0.05)' : undefined,
                    }}
                    onMouseEnter={(e) => showTooltip(e, slice)}
                    onMouseMove={moveTooltip}
                    onMouseLeave={hideTooltip}
                    onClick={() => {
                      if (!slice.isCash && onSelectSymbol) {
                        onSelectSymbol(slice.symbol)
                      }
                    }}
                  >
                    <div className="legend-item-left">
                      <span
                        className="legend-color-dot"
                        style={{ backgroundColor: slice.color, boxShadow: `0 0 6px ${slice.color}88` }}
                      />
                      <div className="legend-item-names">
                        <span className="legend-symbol">{slice.symbol}</span>
                        <span className="legend-name" title={slice.name}>
                          {slice.name}
                        </span>
                      </div>
                    </div>

                    <div className="legend-item-middle">
                      <span className="legend-value">{formatCurrency(slice.value)}</span>
                      {slice.holding && (
                        <span
                          className={`legend-pnl ${slice.holding.livePnL >= 0 ? 'positive' : 'negative'}`}
                        >
                          {formatPercent(slice.holding.livePnLPercent)}
                        </span>
                      )}
                    </div>

                    <div className="legend-item-right">
                      <div className="legend-progress-bar">
                        <div
                          className="legend-progress-fill"
                          style={{
                            width: `${Math.min(100, slice.weightPercent)}%`,
                            backgroundColor: slice.color,
                          }}
                        />
                      </div>
                      <span className="legend-weight">{slice.weightPercent.toFixed(1)}%</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      ) : (
        /* Performance Bar Chart Tab */
        <div className="portfolio-performance-layout">
          <div className="portfolio-performance-desc">
            <p>
              Compare unrealized return (%) and profit/loss contribution across all actively managed positions.
            </p>
            {topHolding && (
              <span className="top-holding-badge">
                Top Holding: <strong>{topHolding.symbol}</strong> ({topHoldingWeight.toFixed(1)}% of portfolio)
              </span>
            )}
          </div>

          <div className="portfolio-bars-list">
            {holdings.length === 0 ? (
              <p className="no-holdings-text">No stock positions in portfolio.</p>
            ) : (
              holdings.map((h, idx) => {
                const color = PALETTE[idx % PALETTE.length]
                const isPositive = h.livePnL >= 0
                const pnlPercent = h.livePnLPercent
                const maxPercent = Math.max(...holdings.map((i) => Math.abs(i.livePnLPercent)), 10)
                const barWidth = Math.min(100, (Math.abs(pnlPercent) / maxPercent) * 100)

                // Match with slice for tooltip
                const sliceMatch = slices.find((s) => s.symbol === h.symbol)

                return (
                  <div
                    key={h.symbol}
                    className="portfolio-bar-row"
                    onMouseEnter={(e) => sliceMatch && showTooltip(e, sliceMatch)}
                    onMouseMove={moveTooltip}
                    onMouseLeave={hideTooltip}
                    onClick={() => onSelectSymbol && onSelectSymbol(h.symbol)}
                  >
                    <div className="bar-row-header">
                      <div className="bar-symbol-info">
                        <span className="bar-color-tag" style={{ backgroundColor: color }} />
                        <strong className="bar-symbol">{h.symbol}</strong>
                        <span className="bar-name">{h.name || h.symbol}</span>
                      </div>
                      <div className="bar-value-info">
                        <span className="bar-market-value">{formatCurrency(h.marketValue)}</span>
                        <span className={`bar-pnl-tag ${isPositive ? 'positive' : 'negative'}`}>
                          {formatCurrency(h.livePnL)} ({formatPercent(h.livePnLPercent)})
                        </span>
                      </div>
                    </div>

                    <div className="bar-track-wrapper">
                      <div className="bar-track">
                        <div
                          className={`bar-fill ${isPositive ? 'positive' : 'negative'}`}
                          style={{
                            width: `${Math.max(4, barWidth)}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}

      {/* Floating Rich Tooltip */}
      <PortfolioTooltip {...tooltipData} />
    </section>
  )
}

export default PortfolioCharts
