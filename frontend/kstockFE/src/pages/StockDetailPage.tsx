import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, Link, useLocation } from 'react-router-dom'
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  type Time,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type TickMarkType,
} from 'lightweight-charts'
import { getSymbolDetail, getSymbols } from '../services/symbol.service'
import type { SymbolBaseDetail, SymbolPreview } from '../types'
import { getLookbackSeconds, useChartHistory } from '../hooks/useChartHistory'
import {
  formatCompactNumber,
  formatDate,
  formatIpoDate,
  formatTickMark,
  isDateOnlyResolution,
  TIMEFRAME_OPTIONS,
  transformOHLCV,
  type CandleData,
  type VolumeData,
} from '../utils/chart'
import { calculateQuoteDetails } from '../utils/quote'
import { useFavorites, useLivePrices } from '../context'
import SymbolNotesPanel from '../components/notes/SymbolNotesPanel'

/** Start fetching older history when fewer than this many bars remain off-screen on the left. */
const LOAD_OLDER_THRESHOLD_BARS = 15

export default function StockDetailPage() {
  const navigate = useNavigate()
  const { symbol: symbolParam } = useParams<{ symbol: string }>()
  const symbol = (symbolParam || 'IBM').toUpperCase()

  const chartContainerRef = useRef<HTMLDivElement | null>(null)
  const chartInstanceRef = useRef<IChartApi | null>(null)
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const candlestickDataRef = useRef<CandleData[]>([])

  const [activeTimeframe, setActiveTimeframe] = useState<
    (typeof TIMEFRAME_OPTIONS)[number]['resolution']
  >('1D')
  // Chart history: cache-first (IndexedDB), lazily pages back in time on scroll.
  const { data, loading, loadingOlder, loadOlder } = useChartHistory(symbol, activeTimeframe)
  const loadOlderRef = useRef(loadOlder)
  const initialRangeAppliedRef = useRef(false)
  const [symbolDetail, setSymbolDetail] = useState<SymbolBaseDetail | null>(null)
  const [fetchedPreview, setFetchedPreview] = useState<SymbolPreview | null>(null)
  const location = useLocation()
  const navigationPreview = (
    location.state as { symbolPreview?: SymbolPreview } | null
  )?.symbolPreview

  // Prefer fresh fetched preview for this symbol if available, otherwise use preview passed via router navigation
  const activeFetched =
    fetchedPreview && fetchedPreview.ticker.toUpperCase() === symbol.toUpperCase()
      ? fetchedPreview
      : null
  const activeNav =
    navigationPreview && navigationPreview.ticker.toUpperCase() === symbol.toUpperCase()
      ? navigationPreview
      : null
  const symbolPreview = activeFetched ?? activeNav

  // Favorites Context integration
  const { isFavorite, toggleFavorite } = useFavorites()
  const [favoriteUpdating, setFavoriteUpdating] = useState(false)
  const [favoriteError, setFavoriteError] = useState<string | null>(null)

  // Live prices hook
  const { prices } = useLivePrices([symbol])
  const liveTick = prices[symbol]

  const [hoverInfo, setHoverInfo] = useState<{
    date?: string
    open?: number
    high?: number
    low?: number
    close?: number
    volume?: number
  } | null>(null)

  useEffect(() => {
    let isMounted = true

    async function loadSymbolData() {
      try {
        const [detailRes, nasdaqRes, nyseRes, generalRes] = await Promise.allSettled([
          getSymbolDetail(symbol),
          getSymbols({ exchange: 'NASDAQ', name: symbol }),
          getSymbols({ exchange: 'NYSE', name: symbol }),
          getSymbols({ name: symbol }),
        ])
        if (!isMounted) return
        if (detailRes.status === 'fulfilled') {
          setSymbolDetail(detailRes.value.data)
        } else {
          setSymbolDetail(null)
        }
        const candidates: SymbolPreview[] = [
          ...(nasdaqRes.status === 'fulfilled' ? (nasdaqRes.value.data ?? []) : []),
          ...(nyseRes.status === 'fulfilled' ? (nyseRes.value.data ?? []) : []),
          ...(generalRes.status === 'fulfilled' ? (generalRes.value.data ?? []) : []),
        ]
        const match = candidates.find(
          (item) => item.ticker.toUpperCase() === symbol.toUpperCase(),
        )
        if (match) {
          setFetchedPreview(match)
        }
      } catch (err) {
        console.warn('Unable to load symbol data:', err)
        if (isMounted) {
          setSymbolDetail(null)
          setFetchedPreview(null)
        }
      }
    }

    loadSymbolData()
    return () => {
      isMounted = false
    }
  }, [symbol])

  useEffect(() => {
    loadOlderRef.current = loadOlder
  }, [loadOlder])

  const { candlestickData, volumeData, items } = useMemo(
    () => (data ? transformOHLCV(data) : { candlestickData: [], volumeData: [], items: [] }),
    [data],
  )

  const lookbackSeconds = getLookbackSeconds(activeTimeframe)
  // 1D / 1W bars: show only the date, no time-of-day.
  const dateOnly = isDateOnlyResolution(activeTimeframe)
  const latestHistoricalItem = items.length > 0 ? items[items.length - 1] : null

  // Synchronized quote calculation matching SymbolListPage
  const quoteData = useMemo(() => {
    return calculateQuoteDetails({
      symbolPreview,
      livePrice: liveTick?.price,
      items,
    })
  }, [symbolPreview, liveTick?.price, items])

  const handleFavoriteToggle = async () => {
    setFavoriteUpdating(true)
    setFavoriteError(null)
    try {
      await toggleFavorite(symbol)
    } catch (err) {
      console.warn('Unable to update favorite:', err)
      setFavoriteError('Unable to update favorite status.')
    } finally {
      setFavoriteUpdating(false)
    }
  }

  // Chart creation effect — runs once per symbol/timeframe (not on every data update),
  // so the user's scroll/zoom position survives lazy-loading of older bars.
  useEffect(() => {
    if (loading || !chartContainerRef.current) return

    const container = chartContainerRef.current
    initialRangeAppliedRef.current = false

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#131722' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#1f293d' },
        horzLines: { color: '#1f293d' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#2b2d3e',
      },
      localization: {
        timeFormatter: (time: Time) => formatDate(time as number, dateOnly),
      },
      timeScale: {
        borderColor: '#2b2d3e',
        timeVisible: !dateOnly,
        secondsVisible: false,
        tickMarkFormatter: (time: Time, tickMarkType: TickMarkType) =>
          formatTickMark(time as number, container.clientWidth < 720, dateOnly, tickMarkType),
        fixLeftEdge: true,
        fixRightEdge: false,
        rightOffsetPixels: Math.min(65, Math.max(30, Math.round(container.clientWidth * 0.08))),
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
      },
      width: container.clientWidth,
      height: container.clientHeight || 500,
    })

    chartInstanceRef.current = chart

    // 1. Candlestick Series for OHLC
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })
    candlestickSeriesRef.current = candlestickSeries

    candlestickSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.05,
        bottom: 0.25, // Upper 75% of chart
      },
    })

    // 2. Histogram Series for Volume
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#26a69a',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    })
    volumeSeriesRef.current = volumeSeries

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.75, // Lower 25% of chart
        bottom: 0,
      },
    })

    // Lazy-load older history when the user scrolls close to the left edge.
    const handleVisibleRangeChange = (range: LogicalRange | null) => {
      if (range && range.from < LOAD_OLDER_THRESHOLD_BARS) {
        void loadOlderRef.current()
      }
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)

    // Crosshair hover listener
    chart.subscribeCrosshairMove((param) => {
      if (
        !param ||
        param.time === undefined ||
        param.point === undefined ||
        param.point.x < 0 ||
        param.point.x > container.clientWidth ||
        param.point.y < 0 ||
        param.point.y > container.clientHeight
      ) {
        setHoverInfo(null)
        return
      }

      const candle = param.seriesData.get(candlestickSeries) as CandleData | undefined
      const vol = param.seriesData.get(volumeSeries) as VolumeData | undefined

      if (candle) {
        setHoverInfo({
          date: formatDate(param.time as number, dateOnly),
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
          volume: vol ? vol.value : undefined,
        })
      }
    })

    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length === 0 || !entries[0].contentRect) return
      const { width, height } = entries[0].contentRect
      const rightMargin = Math.min(65, Math.max(30, Math.round(width * 0.08)))
      chart.applyOptions({ width, height })
      chart.timeScale().applyOptions({ rightOffsetPixels: rightMargin })
      if (candlestickDataRef.current.length > 0) {
        const targetBarsWidth = Math.max(100, width - rightMargin)
        const minSpacing = Math.min(
          Math.floor(width * 0.45),
          Math.max(0.5, targetBarsWidth / candlestickDataRef.current.length)
        )
        chart.timeScale().applyOptions({ minBarSpacing: minSpacing })
      }
    })

    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
      chart.remove()
      chartInstanceRef.current = null
      candlestickSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [loading, symbol, activeTimeframe, dateOnly])

  // Data effect — pushes bars into the existing series. Lightweight Charts keeps the
  // view anchored to the right edge, so prepended (older) bars don't move the viewport.
  useEffect(() => {
    candlestickDataRef.current = candlestickData
    const chart = chartInstanceRef.current
    const candlestickSeries = candlestickSeriesRef.current
    const volumeSeries = volumeSeriesRef.current
    if (!chart || !candlestickSeries || !volumeSeries || candlestickData.length === 0) return

    candlestickSeries.setData(candlestickData)
    volumeSeries.setData(volumeData)

    const containerWidth = chartContainerRef.current?.clientWidth || 800
    const rightMargin = Math.min(65, Math.max(30, Math.round(containerWidth * 0.08)))
    const targetBarsWidth = Math.max(100, containerWidth - rightMargin)
    const minSpacing = Math.min(
      Math.floor(containerWidth * 0.45),
      Math.max(0.5, targetBarsWidth / candlestickData.length),
    )

    chart.timeScale().applyOptions({
      rightOffsetPixels: rightMargin,
      minBarSpacing: minSpacing,
    })

    if (!initialRangeAppliedRef.current) {
      initialRangeAppliedRef.current = true
      // Show the default lookback window even if the cache holds much more history.
      const lastIndex = candlestickData.length - 1
      const windowStart = Number(candlestickData[lastIndex].time) - lookbackSeconds
      const startIndex = Math.max(
        0,
        candlestickData.findIndex((bar) => Number(bar.time) >= windowStart),
      )
      // When available data is limited or falls entirely within the lookback window,
      // fit all content so bars span across the chart width with comfortable right margin.
      if (startIndex === 0 || lastIndex - startIndex < 10) {
        chart.timeScale().fitContent()
      } else {
        chart.timeScale().setVisibleLogicalRange({ from: startIndex, to: lastIndex })
      }
    }
  }, [candlestickData, volumeData, lookbackSeconds, loading, symbol, activeTimeframe])

  const displayedInfo =
    hoverInfo ||
    (latestHistoricalItem
      ? {
          date: formatDate(latestHistoricalItem.time, dateOnly),
          open: latestHistoricalItem.open,
          high: latestHistoricalItem.high,
          low: latestHistoricalItem.low,
          close: quoteData.currentPrice,
          volume: latestHistoricalItem.volume,
        }
      : null)

  const isFav = isFavorite(symbol)

  return (
    <div
      style={{
        backgroundColor: '#0e1117',
        color: '#e1e3e6',
        minHeight: '100vh',
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
        padding: '20px',
      }}
    >
      {/* Header */}
      <header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#131722',
          padding: '16px 24px',
          borderRadius: '8px',
          border: '1px solid #1f293d',
          marginBottom: '16px',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => navigate('/symbols')}
            aria-label="Back to symbol list"
            title="Back to market overview"
            style={{
              background: 'transparent',
              border: 0,
              color: '#9097a6',
              cursor: 'pointer',
              fontSize: '28px',
              lineHeight: 1,
              padding: '4px',
            }}
          >
            ←
          </button>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, letterSpacing: '0.5px' }}>
            {symbolDetail?.ticker || data?.s || symbol}
          </h1>
          <span style={{ fontSize: '28px', fontWeight: 600, color: '#ffffff' }}>
            ${quoteData.currentPrice.toFixed(2)}
          </span>
          <span
            style={{
              fontSize: '16px',
              fontWeight: 600,
              color: quoteData.isPositive ? '#26a69a' : '#ef5350',
              backgroundColor: quoteData.isPositive
                ? 'rgba(38, 166, 154, 0.12)'
                : 'rgba(239, 83, 80, 0.12)',
              padding: '4px 8px',
              borderRadius: '4px',
            }}
          >
            {quoteData.isPositive ? '+' : ''}
            {quoteData.priceChange.toFixed(2)} ({quoteData.isPositive ? '+' : ''}
            {quoteData.percentChange.toFixed(2)}%)
          </span>

          {liveTick && (
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: '#34c293',
                backgroundColor: 'rgba(52, 194, 147, 0.15)',
                padding: '2px 8px',
                borderRadius: '999px',
                border: '1px solid rgba(52, 194, 147, 0.3)',
              }}
            >
              LIVE TICK
            </span>
          )}
        </div>

        {/* Action Controls: Buy, Sell, Alert, Favorite */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            fontSize: '14px',
            flexWrap: 'wrap',
          }}
        >
          <Link
            to={`/trading?symbol=${encodeURIComponent(symbol)}&operation=BUY`}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              background: '#26a69a',
              color: '#07101b',
              fontWeight: 700,
              textDecoration: 'none',
              fontSize: '13.5px',
            }}
          >
            Buy {symbol}
          </Link>

          <Link
            to={`/trading?symbol=${encodeURIComponent(symbol)}&operation=SELL`}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              background: '#ef5350',
              color: '#ffffff',
              fontWeight: 700,
              textDecoration: 'none',
              fontSize: '13.5px',
            }}
          >
            Sell {symbol}
          </Link>

          <Link
            to={`/alerts?symbol=${encodeURIComponent(symbol)}`}
            style={{
              padding: '8px 14px',
              borderRadius: '6px',
              background: 'rgba(124, 92, 255, 0.18)',
              border: '1px solid rgba(124, 92, 255, 0.35)',
              color: '#b8c5ff',
              fontWeight: 600,
              textDecoration: 'none',
              fontSize: '13.5px',
            }}
          >
            ⚡ Set Alert
          </Link>

          <button
            type="button"
            onClick={handleFavoriteToggle}
            disabled={favoriteUpdating}
            aria-pressed={isFav}
            aria-label={isFav ? `Remove ${symbol} from favorites` : `Add ${symbol} to favorites`}
            title={isFav ? 'Remove from favorites' : 'Add to favorites'}
            style={{
              alignItems: 'center',
              backgroundColor: 'transparent',
              border: 0,
              color: isFav ? '#f06292' : '#f8bbd0',
              cursor: favoriteUpdating ? 'wait' : 'pointer',
              display: 'inline-flex',
              fontSize: '34px',
              fontWeight: 700,
              lineHeight: 1,
              padding: '4px',
              transition: 'color 0.15s ease, transform 0.15s ease',
            }}
          >
            {isFav ? '♥' : '♡'}
          </button>
          {favoriteError && (
            <span role="alert" style={{ color: '#ef5350', fontSize: '13px' }}>
              {favoriteError}
            </span>
          )}
        </div>
      </header>

      {symbolDetail && (
        <section
          aria-label="Company information"
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(220px, 1.3fr) repeat(3, minmax(120px, 1fr))',
            gap: '16px',
            alignItems: 'center',
            backgroundColor: '#131722',
            padding: '16px 24px',
            borderRadius: '8px',
            border: '1px solid #1f293d',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
            {symbolDetail.logo && (
              <img
                src={symbolDetail.logo}
                alt=""
                style={{
                  width: '40px',
                  height: '40px',
                  objectFit: 'contain',
                  borderRadius: '4px',
                  backgroundColor: '#ffffff',
                }}
              />
            )}
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  color: '#ffffff',
                  fontSize: '16px',
                  fontWeight: 700,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {symbolDetail.name}
              </div>
              <div style={{ color: '#9097a6', fontSize: '13px', marginTop: '3px' }}>
                {symbolDetail.exchange} · {symbolDetail.industry || 'Industry unavailable'}
              </div>
            </div>
          </div>

          <div
            style={{ color: '#9097a6', fontSize: '13px' }}
            title={
              symbolDetail.marketCapitalization
                ? `Market Capitalization: ${symbolDetail.marketCapitalization.toLocaleString()} ${symbolDetail.currency || ''}`.trim()
                : undefined
            }
          >
            <div>Market cap</div>
            <strong style={{ color: '#ffffff', fontSize: '15px' }}>
              {symbolDetail.marketCapitalization
                ? formatCompactNumber(symbolDetail.marketCapitalization)
                : 'N/A'}
            </strong>
          </div>
          <div
            style={{ color: '#9097a6', fontSize: '13px' }}
            title={
              symbolDetail.shareOutstanding
                ? `Shares Outstanding: ${symbolDetail.shareOutstanding.toLocaleString()} shares`
                : undefined
            }
          >
            <div>Shares outstanding</div>
            <strong style={{ color: '#ffffff', fontSize: '15px' }}>
              {symbolDetail.shareOutstanding
                ? formatCompactNumber(symbolDetail.shareOutstanding)
                : 'N/A'}
            </strong>
          </div>
          <div
            style={{ color: '#9097a6', fontSize: '13px' }}
            title="IPO Date · Country · Currency"
          >
            <div>IPO · Country · Currency</div>
            <strong style={{ color: '#ffffff', fontSize: '15px' }}>
              {[formatIpoDate(symbolDetail.ipo), symbolDetail.country, symbolDetail.currency]
                .filter(Boolean)
                .join(' · ') || 'N/A'}
            </strong>
          </div>

          {(symbolDetail.phone || symbolDetail.weburl) && (
            <div
              style={{
                gridColumn: '1 / -1',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '16px',
                color: '#9097a6',
                fontSize: '13px',
              }}
            >
              {symbolDetail.phone && <span>{symbolDetail.phone}</span>}
              {symbolDetail.weburl && (
                <a
                  href={symbolDetail.weburl}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: '#4d8dff' }}
                >
                  Website
                </a>
              )}
            </div>
          )}
        </section>
      )}

      <div style={{ alignItems: 'stretch', display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
        <SymbolNotesPanel key={symbol} symbol={symbol} />


        <div style={{ display: 'flex', flex: '1 1 680px', flexDirection: 'column', minWidth: 0 }}>
          {/* Timeframe toolbar & hover breakdown */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: '#131722',
              padding: '12px 20px',
              borderRadius: '8px 8px 0 0',
              border: '1px solid #1f293d',
              borderBottom: 'none',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', gap: '6px' }}>
              {TIMEFRAME_OPTIONS.map((timeframe) => (
                <button
                  key={timeframe.resolution}
                  onClick={() => setActiveTimeframe(timeframe.resolution)}
                  style={{
                    backgroundColor:
                      activeTimeframe === timeframe.resolution ? '#2962ff' : 'transparent',
                    color: activeTimeframe === timeframe.resolution ? '#ffffff' : '#787b86',
                    border: 'none',
                    padding: '6px 12px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '13px',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {timeframe.label}
                </button>
              ))}
            </div>

            {/* OHLCV hover info legend */}
            {displayedInfo && (
              <div
                style={{
                  display: 'flex',
                  gap: '16px',
                  fontSize: '13px',
                  fontFamily: 'monospace',
                  flexWrap: 'wrap',
                }}
              >
                <span
                  title="Date: Timestamp of this bar"
                  style={{ color: '#787b86', cursor: 'help' }}
                >
                  Date: <strong style={{ color: '#d1d4dc' }}>{displayedInfo.date}</strong>
                </span>
                <span
                  title="Open: Opening price for this period"
                  style={{ color: '#787b86', cursor: 'help' }}
                >
                  Open: <strong style={{ color: '#d1d4dc' }}>{displayedInfo.open?.toFixed(2)}</strong>
                </span>
                <span
                  title="High: Highest price recorded in this period"
                  style={{ color: '#787b86', cursor: 'help' }}
                >
                  High: <strong style={{ color: '#26a69a' }}>{displayedInfo.high?.toFixed(2)}</strong>
                </span>
                <span
                  title="Low: Lowest price recorded in this period"
                  style={{ color: '#787b86', cursor: 'help' }}
                >
                  Low: <strong style={{ color: '#ef5350' }}>{displayedInfo.low?.toFixed(2)}</strong>
                </span>
                <span
                  title="Close: Closing price of this period"
                  style={{ color: '#787b86', cursor: 'help' }}
                >
                  Close:{' '}
                  <strong style={{ color: '#d1d4dc' }}>{displayedInfo.close?.toFixed(2)}</strong>
                </span>
                <span
                  title="Volume: Total volume of shares traded"
                  style={{ color: '#787b86', cursor: 'help' }}
                >
                  Volume:{' '}
                  <strong style={{ color: '#d1d4dc' }}>
                    {displayedInfo.volume?.toLocaleString()}
                  </strong>
                </span>
              </div>
            )}
          </div>

          {/* Main Chart Container */}
          <div
            style={{
              flex: 1,
              minHeight: '520px',
              backgroundColor: '#131722',
              borderRadius: '0 0 8px 8px',
              border: '1px solid #1f293d',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {loading ? (
              <div
                style={{
                  display: 'flex',
                  height: '100%',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#787b86',
                }}
              >
                Loading stock chart...
              </div>
            ) : (
              <div
                ref={chartContainerRef}
                style={{ width: '100%', height: '100%', minHeight: '520px' }}
              />
            )}
            {!loading && loadingOlder && (
              <div
                role="status"
                style={{
                  position: 'absolute',
                  top: '10px',
                  left: '10px',
                  zIndex: 3,
                  padding: '4px 10px',
                  borderRadius: '999px',
                  fontSize: '12px',
                  color: '#b8c5ff',
                  backgroundColor: 'rgba(41, 98, 255, 0.18)',
                  border: '1px solid rgba(41, 98, 255, 0.4)',
                  pointerEvents: 'none',
                }}
              >
                Loading older data…
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
