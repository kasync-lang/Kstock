import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import { getChartHistory } from '../services/chart.service';

export interface OHLCVResponse {
  s: string;
  t: number[];
  o: number[];
  h: number[];
  l: number[];
  c: number[];
  v: number[];
}

export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface VolumeData {
  time: number;
  value: number;
  color?: string;
}

export interface TransformedItem extends CandleData {
  volume: number;
}

export const MOCK_OHLCV_DATA: OHLCVResponse = {
  s: 'Demos',
  t: [1784505600, 1784592000, 1784678400, 1784764800],
  o: [210.07, 210.72, 207.68, 202.64],
  h: [216.2762, 214.97, 212.3417, 207.55],
  l: [208.82, 209.18, 204.73, 199.19],
  c: [213, 210.5, 205.77, 206.65],
  v: [9585016, 11954411, 14606736, 15306010],
};

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
    return { candlestickData: [], volumeData: [], items: [] };
  }

  const len = response.t.length;
  if (
    response.o.length !== len ||
    response.h.length !== len ||
    response.l.length !== len ||
    response.c.length !== len ||
    response.v.length !== len
  ) {
    console.error('OHLCV array length mismatch across parallel arrays');
    return { candlestickData: [], volumeData: [], items: [] };
  }

  const items: TransformedItem[] = response.t.map((timestamp, index) => {
    // Normalize milliseconds to seconds if necessary (> 1e11 indicates timestamp in ms)
    const normalizedTime = timestamp > 1e11 ? Math.floor(timestamp / 1000) : timestamp;
    return {
      time: normalizedTime,
      open: response.o[index],
      high: response.h[index],
      low: response.l[index],
      close: response.c[index],
      volume: response.v[index],
    };
  });

  // 1. Ensure timestamps are sorted in strictly ascending order
  items.sort((a, b) => (a.time as number) - (b.time as number));

  // 2. Filter out duplicate timestamps to prevent Lightweight Charts Assertion Failure
  const uniqueItems = items.filter(
    (item, index, self) => index === 0 || (item.time as number) > (self[index - 1].time as number)
  );

  const candlestickData: CandleData[] = uniqueItems.map((item) => ({
    time: item.time,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
  }));

  const volumeData: VolumeData[] = uniqueItems.map((item) => ({
    time: item.time,
    value: item.volume,
    color: item.close >= item.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
  }));

  return { candlestickData, volumeData, items: uniqueItems };
}

export function formatDate(timestamp: number | string): string {
  const date = new Date(Number(timestamp) * 1000);
  if (isNaN(date.getTime())) return String(timestamp);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function StockDetailPage() {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState<string>('1D');
  const [data, setData] = useState<OHLCVResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [hoverInfo, setHoverInfo] = useState<{
    date?: string;
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
  } | null>(null);

  // Fetch OHLCV data from API with mock fallback
  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      try {
        const now = Math.floor(Date.now() / 1000);
        const oneDay = 86400 * 30; // 30 days default range
        const json = await getChartHistory({
          symbol: 'IBM',
          resolution: activeTimeframe,
          from: now - oneDay,
          to: now,
        });
        if (!json || !json.t || json.t.length === 0) {
          throw new Error('Empty response');
        }
        if (isMounted) setData(json);
      } catch (err) {
        console.warn('API fetch failed, falling back to mock data:', err);
        if (isMounted) setData(MOCK_OHLCV_DATA);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [activeTimeframe]);

  const { candlestickData, volumeData, items } = data
    ? transformOHLCV(data)
    : { candlestickData: [], volumeData: [], items: [] };

  const firstClose = items.length > 0 ? items[0].close : 0;
  const latestItem = items.length > 0 ? items[items.length - 1] : null;
  const latestClose = latestItem ? latestItem.close : 0;
  const priceChange = latestClose - firstClose;
  const percentChange = firstClose !== 0 ? (priceChange / firstClose) * 100 : 0;
  const isPositive = priceChange >= 0;

  // Chart rendering effect
  useEffect(() => {
    if (!chartContainerRef.current || candlestickData.length === 0) return;

    const container = chartContainerRef.current;

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
      timeScale: {
        borderColor: '#2b2d3e',
        timeVisible: true,
        secondsVisible: false,
      },
      width: container.clientWidth,
      height: container.clientHeight || 500,
    });

    // 1. Candlestick Series for OHLC (Upper chart section)
    const candlestickSeries =
      typeof (chart as any).addSeries === 'function' && CandlestickSeries
        ? (chart as any).addSeries(CandlestickSeries, {
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderVisible: false,
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
        })
        : (chart as any).addCandlestickSeries({
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderVisible: false,
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
        });

    candlestickSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.05,
        bottom: 0.25, // Upper 75% of chart
      },
    });

    // 2. Histogram Series for Volume (Lower chart section, sharing same horizontal time scale)
    const volumeSeries =
      typeof (chart as any).addSeries === 'function' && HistogramSeries
        ? (chart as any).addSeries(HistogramSeries, {
          color: '#26a69a',
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: '',
        })
        : (chart as any).addHistogramSeries({
          color: '#26a69a',
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: '',
        });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.75, // Lower 25% of chart
        bottom: 0,
      },
    });

    candlestickSeries.setData(candlestickData);
    volumeSeries.setData(volumeData);
    chart.timeScale().fitContent();

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
        setHoverInfo(null);
        return;
      }

      const candle = param.seriesData.get(candlestickSeries) as CandleData | undefined;
      const vol = param.seriesData.get(volumeSeries) as VolumeData | undefined;

      if (candle) {
        setHoverInfo({
          date: formatDate(param.time as number),
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
          volume: vol ? vol.value : undefined,
        });
      }
    });

    // ResizeObserver for responsive chart
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length === 0 || !entries[0].contentRect) return;
      const { width, height } = entries[0].contentRect;
      chart.applyOptions({ width, height });
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [candlestickData, volumeData]);

  const displayedInfo = hoverInfo || (latestItem ? {
    date: formatDate(latestItem.time),
    open: latestItem.open,
    high: latestItem.high,
    low: latestItem.low,
    close: latestItem.close,
    volume: latestItem.volume,
  } : null);

  return (
    <div
      style={{
        backgroundColor: '#0e1117',
        color: '#e1e3e6',
        minHeight: '100vh',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif',
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
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px' }}>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, letterSpacing: '0.5px' }}>
            {data?.s || 'IBM'}
          </h1>
          <span style={{ fontSize: '28px', fontWeight: 600, color: '#ffffff' }}>
            ${latestClose.toFixed(2)}
          </span>
          <span
            style={{
              fontSize: '16px',
              fontWeight: 600,
              color: isPositive ? '#26a69a' : '#ef5350',
              backgroundColor: isPositive ? 'rgba(38, 166, 154, 0.12)' : 'rgba(239, 83, 80, 0.12)',
              padding: '4px 8px',
              borderRadius: '4px',
            }}
          >
            {isPositive ? '+' : ''}
            {priceChange.toFixed(2)} ({isPositive ? '+' : ''}
            {percentChange.toFixed(2)}%)
          </span>
        </div>

        <div style={{ display: 'flex', gap: '20px', fontSize: '14px', color: '#9097a6' }}>
          <div>
            <span>Vol: </span>
            <strong style={{ color: '#ffffff' }}>
              {latestItem ? latestItem.volume.toLocaleString() : 'N/A'}
            </strong>
          </div>
        </div>
      </header>

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
        }}
      >
        <div style={{ display: 'flex', gap: '6px' }}>
          {['1D', '1W', '1M', '3M', '1Y', 'ALL'].map((tf) => (
            <button
              key={tf}
              onClick={() => setActiveTimeframe(tf)}
              style={{
                backgroundColor: activeTimeframe === tf ? '#2962ff' : 'transparent',
                color: activeTimeframe === tf ? '#ffffff' : '#787b86',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                transition: 'all 0.2s ease',
              }}
            >
              {tf}
            </button>
          ))}
        </div>

        {/* OHLCV hover info legend */}
        {displayedInfo && (
          <div style={{ display: 'flex', gap: '16px', fontSize: '13px', fontFamily: 'monospace' }}>
            <span style={{ color: '#787b86' }}>
              Date: <strong style={{ color: '#d1d4dc' }}>{displayedInfo.date}</strong>
            </span>
            <span style={{ color: '#787b86' }}>
              O: <strong style={{ color: '#d1d4dc' }}>{displayedInfo.open?.toFixed(2)}</strong>
            </span>
            <span style={{ color: '#787b86' }}>
              H: <strong style={{ color: '#26a69a' }}>{displayedInfo.high?.toFixed(2)}</strong>
            </span>
            <span style={{ color: '#787b86' }}>
              L: <strong style={{ color: '#ef5350' }}>{displayedInfo.low?.toFixed(2)}</strong>
            </span>
            <span style={{ color: '#787b86' }}>
              C: <strong style={{ color: '#d1d4dc' }}>{displayedInfo.close?.toFixed(2)}</strong>
            </span>
            <span style={{ color: '#787b86' }}>
              V: <strong style={{ color: '#d1d4dc' }}>{displayedInfo.volume?.toLocaleString()}</strong>
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
          <div ref={chartContainerRef} style={{ width: '100%', height: '100%', minHeight: '520px' }} />
        )}
      </div>
    </div>
  );
}
