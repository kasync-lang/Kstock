/**
 * Browser-side cache for OHLCV chart history.
 *
 * Bars are persisted in IndexedDB (one record per `symbol:resolution`) so that
 * history the user already scrolled through is not downloaded again on the
 * next visit. IndexedDB is used instead of localStorage because history for
 * intraday resolutions easily exceeds the ~5MB localStorage quota.
 */

import type { OHLCVResponse } from '../types'

const DB_NAME = 'kstock-chart-cache'
const DB_VERSION = 1
const STORE_NAME = 'ohlcv'

/** Max number of symbol/resolution records kept; least recently used are evicted. */
const MAX_ENTRIES = 60
/** Max bars kept per record to bound storage usage. Oldest bars are dropped first. */
const MAX_BARS_PER_ENTRY = 50_000

export interface CachedChartHistory {
  key: string
  symbol: string
  resolution: string
  /** Columnar bars, sorted ascending by time with unique timestamps (seconds). */
  data: OHLCVResponse
  /** Earliest `from` (unix seconds) that has already been requested from the API. */
  oldestRequestedFrom: number
  /** True when the API returned no older data — nothing more to lazy-load. */
  reachedStart: boolean
  updatedAt: number
}

export function chartCacheKey(symbol: string, resolution: string): string {
  return `${symbol.toUpperCase()}:${resolution}`
}

let dbPromise: Promise<IDBDatabase | null> | null = null

function openDb(): Promise<IDBDatabase | null> {
  if (dbPromise) return dbPromise

  dbPromise = new Promise((resolve) => {
    if (typeof indexedDB === 'undefined') {
      resolve(null)
      return
    }
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION)
      request.onupgradeneeded = () => {
        const db = request.result
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' })
          store.createIndex('updatedAt', 'updatedAt')
        }
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => {
        console.warn('Chart cache unavailable:', request.error)
        resolve(null)
      }
      request.onblocked = () => resolve(null)
    } catch (err) {
      console.warn('Chart cache unavailable:', err)
      resolve(null)
    }
  })

  return dbPromise
}

export async function readChartCache(
  symbol: string,
  resolution: string,
): Promise<CachedChartHistory | null> {
  const db = await openDb()
  if (!db) return null

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const request = tx.objectStore(STORE_NAME).get(chartCacheKey(symbol, resolution))
      request.onsuccess = () => resolve((request.result as CachedChartHistory) ?? null)
      request.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

export async function writeChartCache(
  entry: Omit<CachedChartHistory, 'key' | 'updatedAt'>,
): Promise<void> {
  const db = await openDb()
  if (!db) return

  const data = trimBars(entry.data, MAX_BARS_PER_ENTRY)
  const trimmed = data.t.length !== entry.data.t.length
  const record: CachedChartHistory = {
    ...entry,
    data,
    // If bars were dropped we no longer hold the oldest history.
    oldestRequestedFrom: trimmed ? data.t[0] : entry.oldestRequestedFrom,
    reachedStart: trimmed ? false : entry.reachedStart,
    key: chartCacheKey(entry.symbol, entry.resolution),
    updatedAt: Date.now(),
  }

  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      tx.objectStore(STORE_NAME).put(record)
      tx.oncomplete = () => resolve()
      tx.onerror = () => {
        console.warn('Unable to persist chart cache:', tx.error)
        resolve()
      }
      tx.onabort = () => resolve()
    } catch (err) {
      console.warn('Unable to persist chart cache:', err)
      resolve()
    }
  })

  void evictOldEntries(db)
}

async function evictOldEntries(db: IDBDatabase): Promise<void> {
  try {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const countRequest = store.count()
    countRequest.onsuccess = () => {
      let excess = countRequest.result - MAX_ENTRIES
      if (excess <= 0) return
      // Walk from least recently updated and delete until within the limit.
      const cursorRequest = store.index('updatedAt').openCursor()
      cursorRequest.onsuccess = () => {
        const cursor = cursorRequest.result
        if (!cursor || excess <= 0) return
        cursor.delete()
        excess -= 1
        cursor.continue()
      }
    }
  } catch {
    // Eviction is best-effort.
  }
}

// ─── Columnar OHLCV helpers ───────────────────────────────────────────────────

function normalizeTime(timestamp: number): number {
  return timestamp > 1e11 ? Math.floor(timestamp / 1000) : timestamp
}

export function emptyOHLCV(symbol: string): OHLCVResponse {
  return { s: symbol, t: [], o: [], h: [], l: [], c: [], v: [] }
}

export function isValidOHLCV(response: OHLCVResponse | null | undefined): response is OHLCVResponse {
  if (!response || !Array.isArray(response.t)) return false
  const len = response.t.length
  return (
    Array.isArray(response.o) && response.o.length === len &&
    Array.isArray(response.h) && response.h.length === len &&
    Array.isArray(response.l) && response.l.length === len &&
    Array.isArray(response.c) && response.c.length === len &&
    Array.isArray(response.v) && response.v.length === len
  )
}

/**
 * Merge two OHLCV payloads. Bars from `incoming` override bars in `base`
 * that share the same timestamp (so a re-fetched, still-forming candle wins).
 * Result is sorted ascending with unique timestamps.
 */
export function mergeOHLCV(base: OHLCVResponse, incoming: OHLCVResponse): OHLCVResponse {
  const byTime = new Map<number, [number, number, number, number, number]>()

  const add = (src: OHLCVResponse) => {
    if (!isValidOHLCV(src)) return
    for (let i = 0; i < src.t.length; i += 1) {
      byTime.set(normalizeTime(src.t[i]), [src.o[i], src.h[i], src.l[i], src.c[i], src.v[i]])
    }
  }
  add(base)
  add(incoming)

  const times = Array.from(byTime.keys()).sort((a, b) => a - b)
  const result = emptyOHLCV(incoming.s || base.s)
  for (const time of times) {
    const [o, h, l, c, v] = byTime.get(time)!
    result.t.push(time)
    result.o.push(o)
    result.h.push(h)
    result.l.push(l)
    result.c.push(c)
    result.v.push(v)
  }
  return result
}

function trimBars(data: OHLCVResponse, maxBars: number): OHLCVResponse {
  if (data.t.length <= maxBars) return data
  const start = data.t.length - maxBars
  return {
    s: data.s,
    t: data.t.slice(start),
    o: data.o.slice(start),
    h: data.h.slice(start),
    l: data.l.slice(start),
    c: data.c.slice(start),
    v: data.v.slice(start),
  }
}

