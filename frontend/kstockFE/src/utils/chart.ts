import { TickMarkType, type Time, type UTCTimestamp } from 'lightweight-charts'

export interface OHLCVResponse {
  s: string
  t: number[]
  o: number[]
  h: number[]
  l: number[]
  c: number[]
  v: number[]
}

export interface CandleData {
  time: Time
  open: number
  high: number
  low: number
  close: number
}

export interface VolumeData {
  time: Time
  value: number
  color?: string
}

export interface TransformedItem {
  time: Time
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export const US_MARKET_TIME_ZONE = 'America/New_York'

export const TIMEFRAME_OPTIONS = [
  { label: '1m', resolution: '1m', lookbackSeconds: 60 * 60 * 24 },
  { label: '5m', resolution: '5m', lookbackSeconds: 60 * 60 * 24 * 5 },
  { label: '15m', resolution: '15m', lookbackSeconds: 60 * 60 * 24 * 14 },
  { label: '1h', resolution: '1h', lookbackSeconds: 60 * 60 * 24 * 90 },
  { label: '1D', resolution: '1D', lookbackSeconds: 60 * 60 * 24 * 365 },
  { label: '1W', resolution: '1W', lookbackSeconds: 60 * 60 * 24 * 365 * 5 },
] as const

export const MOCK_OHLCV_DATA: OHLCVResponse = {
  s: 'Demos',
  t: [1784505600, 1784592000, 1784678400, 1784764800],
  o: [210.07, 210.72, 207.68, 202.64],
  h: [216.2762, 214.97, 212.3417, 207.55],
  l: [208.82, 209.18, 204.73, 199.19],
  c: [213, 210.5, 205.77, 206.65],
  v: [9585016, 11954411, 14606736, 15306010],
}

/**
 * Data transformation function specified by API requirements
 */
export function transformOHLCV(response: OHLCVResponse) {
  if (
    !response ||
    !Array.isArray(response.t) ||
    !Array.isArray(response.o) ||
    !Array.isArray(response.h) ||
    !Array.isArray(response.l) ||
    !Array.isArray(response.c) ||
    !Array.isArray(response.v)
  ) {
    return { candlestickData: [], volumeData: [], items: [] }
  }

  const len = response.t.length
  if (
    response.o.length !== len ||
    response.h.length !== len ||
    response.l.length !== len ||
    response.c.length !== len ||
    response.v.length !== len
  ) {
    console.error('OHLCV array length mismatch across parallel arrays')
    return { candlestickData: [], volumeData: [], items: [] }
  }

  const items: TransformedItem[] = response.t.map((timestamp, index) => {
    const normalizedTime = (
      timestamp > 1e11 ? Math.floor(timestamp / 1000) : timestamp
    ) as UTCTimestamp
    return {
      time: normalizedTime,
      open: response.o[index],
      high: response.h[index],
      low: response.l[index],
      close: response.c[index],
      volume: response.v[index],
    }
  })

  // 1. Ensure timestamps are sorted in strictly ascending order
  items.sort((a, b) => (Number(a.time) - Number(b.time)))

  // 2. Filter out duplicate timestamps to prevent Lightweight Charts Assertion Failure
  const uniqueItems = items.filter(
    (item, index, self) => index === 0 || Number(item.time) > Number(self[index - 1].time),
  )

  const candlestickData: CandleData[] = uniqueItems.map((item) => ({
    time: item.time,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
  }))

  const volumeData: VolumeData[] = uniqueItems.map((item) => ({
    time: item.time,
    value: item.volume,
    color: item.close >= item.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
  }))

  return { candlestickData, volumeData, items: uniqueItems }
}

/** Daily/weekly bars represent a whole session, so only the date is meaningful. */
export function isDateOnlyResolution(resolution: string): boolean {
  return resolution === '1D' || resolution === '1W'
}

/*
 * Daily/weekly bar timestamps are session dates (typically 00:00 UTC). Formatting them
 * in New York time would shift them to the previous evening, so date-only labels use UTC.
 */
const DATE_ONLY_TIME_ZONE = 'UTC'

export function formatDate(timestamp: number | string | Time, dateOnly = false): string {
  const date = new Date(Number(timestamp) * 1000)
  if (isNaN(date.getTime())) return String(timestamp)
  if (dateOnly) {
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone: DATE_ONLY_TIME_ZONE,
    })
  }
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: false,
    timeZoneName: 'short',
    timeZone: US_MARKET_TIME_ZONE,
  })
}

export function formatTickMark(
  timestamp: number | Time,
  isCompact: boolean,
  dateOnly = false,
  tickMarkType?: TickMarkType,
): string {
  const date = new Date(Number(timestamp) * 1000)
  if (isNaN(date.getTime())) return String(timestamp)

  if (dateOnly) {
    if (tickMarkType === TickMarkType.Year) {
      return date.toLocaleDateString('en-US', { year: 'numeric', timeZone: DATE_ONLY_TIME_ZONE })
    }
    if (tickMarkType === TickMarkType.Month) {
      return date.toLocaleDateString('en-US', { month: 'short', timeZone: DATE_ONLY_TIME_ZONE })
    }
    return date.toLocaleDateString('en-US', {
      day: '2-digit',
      month: 'short',
      timeZone: DATE_ONLY_TIME_ZONE,
    })
  }

  return date.toLocaleString('en-US', {
    ...(isCompact
      ? {}
      : {
          day: '2-digit',
          month: 'short',
        }),
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: US_MARKET_TIME_ZONE,
  })
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

/**
 * Formats an IPO date string by stripping the time component
 * (e.g., '2012-05-18T00:00:00Z' or '2012-05-18 00:00:00' -> '2012-05-18').
 */
export function formatIpoDate(ipo?: string | null): string {
  if (!ipo) return ''
  const trimmed = String(ipo).trim()
  if (!trimmed) return ''
  return trimmed.split('T')[0].split(' ')[0]
}

