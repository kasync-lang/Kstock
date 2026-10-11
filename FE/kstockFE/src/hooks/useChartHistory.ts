import { useCallback, useEffect, useRef, useState } from 'react'
import { getChartHistory } from '../services/chart.service'
import type { ChartResolution, OHLCVResponse } from '../types'
import { MOCK_OHLCV_DATA, TIMEFRAME_OPTIONS } from '../utils/chart'
import {
  chartCacheKey,
  emptyOHLCV,
  isValidOHLCV,
  mergeOHLCV,
  readChartCache,
  writeChartCache,
} from '../utils/chartCache'

/** How many consecutive empty windows we walk back before assuming history has ended. */
const MAX_EMPTY_WINDOWS = 4
/** Cool-down after a failed "load older" request before auto-retrying on scroll. */
const RETRY_COOLDOWN_MS = 5000
/**
 * If the cached tail is older than `lookback * STALE_FACTOR`, the cache is
 * discarded instead of back-filling a huge gap in a single request.
 */
const STALE_FACTOR = 3

export function getLookbackSeconds(resolution: string): number {
  return (
    TIMEFRAME_OPTIONS.find((option) => option.resolution === resolution)?.lookbackSeconds ??
    60 * 60 * 24 * 30
  )
}

interface HistoryState {
  key: string
  data: OHLCVResponse | null
  loading: boolean
  loadingOlder: boolean
  hasMore: boolean
  isMock: boolean
}

interface MutableHistory {
  key: string
  data: OHLCVResponse | null
  oldestRequestedFrom: number
  reachedStart: boolean
  isMock: boolean
  loadingOlder: boolean
  lastFailureAt: number
}

/**
 * Loads OHLCV history for a symbol/resolution with:
 *  - instant render from the IndexedDB cache (if any),
 *  - a background refresh of the most recent bars,
 *  - `loadOlder()` to lazily page further back in time (cached as well).
 */
export function useChartHistory(symbol: string, resolution: ChartResolution) {
  const key = chartCacheKey(symbol, resolution)

  const [state, setState] = useState<HistoryState>({
    key: '',
    data: null,
    loading: true,
    loadingOlder: false,
    hasMore: false,
    isMock: false,
  })

  const historyRef = useRef<MutableHistory>({
    key: '',
    data: null,
    oldestRequestedFrom: 0,
    reachedStart: false,
    isMock: false,
    loadingOlder: false,
    lastFailureAt: 0,
  })

  // Initial load: cache first, then refresh the newest bars from the API.
  useEffect(() => {
    let cancelled = false
    const lookback = getLookbackSeconds(resolution)

    historyRef.current = {
      key,
      data: null,
      oldestRequestedFrom: 0,
      reachedStart: false,
      isMock: false,
      loadingOlder: false,
      lastFailureAt: 0,
    }

    const publish = (patch: Partial<HistoryState>) => {
      if (cancelled) return
      setState((prev) => ({
        ...(prev.key === key
          ? prev
          : { key, data: null, loading: true, loadingOlder: false, hasMore: false, isMock: false }),
        ...patch,
      }))
    }

    async function load() {
      const now = Math.floor(Date.now() / 1000)
      const cached = await readChartCache(symbol, resolution)
      if (cancelled) return

      let current: OHLCVResponse | null = null
      let oldestRequestedFrom = now - lookback
      let reachedStart = false

      if (cached && isValidOHLCV(cached.data) && cached.data.t.length > 0) {
        const lastCachedTime = cached.data.t[cached.data.t.length - 1]
        if (now - lastCachedTime <= lookback * STALE_FACTOR) {
          current = cached.data
          oldestRequestedFrom = Math.min(cached.oldestRequestedFrom, cached.data.t[0])
          reachedStart = cached.reachedStart
        }
      }

      const ref = historyRef.current
      ref.data = current
      ref.oldestRequestedFrom = oldestRequestedFrom
      ref.reachedStart = reachedStart

      if (current) {
        publish({ data: current, loading: false, hasMore: !reachedStart, isMock: false })
      } else {
        publish({ data: null, loading: true, hasMore: false, isMock: false })
      }

      // Re-fetch from the last cached bar (inclusive) so a still-forming candle is updated.
      const tailFrom = current ? current.t[current.t.length - 1] : now - lookback
      try {
        const fresh = await getChartHistory({ symbol, resolution, from: tailFrom, to: now })
        if (cancelled) return

        if (isValidOHLCV(fresh) && fresh.t.length > 0) {
          current = mergeOHLCV(current ?? emptyOHLCV(symbol), fresh)
        }
        if (!current || current.t.length === 0) {
          throw new Error('Empty response')
        }

        ref.data = current
        publish({ data: current, loading: false, hasMore: !reachedStart, isMock: false })
        void writeChartCache({ symbol, resolution, data: current, oldestRequestedFrom, reachedStart })
      } catch (err) {
        if (cancelled) return
        if (current) {
          console.warn('Chart refresh failed, showing cached data:', err)
          publish({ loading: false })
        } else {
          console.warn('API fetch failed, falling back to mock data:', err)
          ref.data = MOCK_OHLCV_DATA
          ref.isMock = true
          publish({ data: MOCK_OHLCV_DATA, loading: false, hasMore: false, isMock: true })
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [key, symbol, resolution])

  const loadOlder = useCallback(async () => {
    const ref = historyRef.current
    if (ref.key !== key || !ref.data || ref.loadingOlder || ref.reachedStart || ref.isMock) return
    if (Date.now() - ref.lastFailureAt < RETRY_COOLDOWN_MS) return

    const lookback = getLookbackSeconds(resolution)
    const isCurrent = () => historyRef.current === ref

    ref.loadingOlder = true
    setState((prev) => (prev.key === key ? { ...prev, loadingOlder: true } : prev))

    try {
      let merged = ref.data
      let oldest = ref.oldestRequestedFrom
      let gotBars = false

      // Walk back window by window; skip over gaps such as weekends/holidays.
      for (let step = 0; step < MAX_EMPTY_WINDOWS && oldest > 0; step += 1) {
        const to = oldest - 1
        const from = Math.max(0, oldest - lookback)
        const older = await getChartHistory({ symbol, resolution, from, to })
        if (!isCurrent()) return

        oldest = from
        if (isValidOHLCV(older) && older.t.length > 0) {
          merged = mergeOHLCV(merged, older)
          gotBars = true
          break
        }
      }

      ref.data = merged
      ref.oldestRequestedFrom = oldest
      ref.reachedStart = !gotBars || oldest <= 0

      setState((prev) =>
        prev.key === key ? { ...prev, data: merged, hasMore: !ref.reachedStart } : prev,
      )
      void writeChartCache({
        symbol,
        resolution,
        data: merged,
        oldestRequestedFrom: ref.oldestRequestedFrom,
        reachedStart: ref.reachedStart,
      })
    } catch (err) {
      console.warn('Unable to load older chart data:', err)
      ref.lastFailureAt = Date.now()
    } finally {
      ref.loadingOlder = false
      if (isCurrent()) {
        setState((prev) => (prev.key === key ? { ...prev, loadingOlder: false } : prev))
      }
    }
  }, [key, symbol, resolution])

  // Hide state that belongs to a previous symbol/resolution until the new one is loaded.
  const isCurrentKey = state.key === key
  return {
    data: isCurrentKey ? state.data : null,
    loading: isCurrentKey ? state.loading : true,
    loadingOlder: isCurrentKey && state.loadingOlder,
    hasMore: isCurrentKey && state.hasMore,
    isMock: isCurrentKey && state.isMock,
    loadOlder,
  }
}

