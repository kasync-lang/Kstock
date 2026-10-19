import React, { useLayoutEffect, useRef, useState } from 'react'
import './PortfolioTooltip.css'

export interface TooltipMetric {
  label: string
  value: string
  highlight?: 'positive' | 'negative' | 'neutral' | 'accent' | 'cash'
}

export interface PortfolioTooltipProps {
  visible: boolean
  x: number
  y: number
  title: string
  subtitle?: string
  badge?: string
  color?: string
  metrics: TooltipMetric[]
  footer?: string
}

export const PortfolioTooltip: React.FC<PortfolioTooltipProps> = ({
  visible,
  x,
  y,
  title,
  subtitle,
  badge,
  color = '#7c5cff',
  metrics,
  footer,
}) => {
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<{ left: number; top: number }>({ left: x, top: y })

  useLayoutEffect(() => {
    if (!visible || !tooltipRef.current) return

    const tooltipEl = tooltipRef.current
    const rect = tooltipEl.getBoundingClientRect()
    const padding = 16

    // Default: slightly above and to the right of cursor
    let targetLeft = x + 16
    let targetTop = y - rect.height - 12

    // Check right edge
    if (targetLeft + rect.width > window.innerWidth - padding) {
      targetLeft = x - rect.width - 16
    }
    // Check left edge
    if (targetLeft < padding) {
      targetLeft = padding
    }

    // Check top edge
    if (targetTop < padding) {
      targetTop = y + 20 // flip below cursor
    }
    // Check bottom edge
    if (targetTop + rect.height > window.innerHeight - padding) {
      targetTop = window.innerHeight - rect.height - padding
    }

    setCoords({ left: targetLeft, top: targetTop })
  }, [x, y, visible, metrics, title])

  if (!visible) return null

  return (
    <div
      ref={tooltipRef}
      className="portfolio-floating-tooltip"
      style={{
        left: `${coords.left}px`,
        top: `${coords.top}px`,
        borderColor: `${color}55`,
        boxShadow: `0 16px 36px rgba(0, 0, 0, 0.65), 0 0 20px ${color}25`,
      }}
      role="tooltip"
      aria-hidden={!visible}
    >
      <div className="tooltip-header">
        <div className="tooltip-title-row">
          <span className="tooltip-color-indicator" style={{ backgroundColor: color }} />
          <h4 className="tooltip-title">{title}</h4>
          {badge && (
            <span
              className="tooltip-badge"
              style={{
                backgroundColor: `${color}20`,
                borderColor: `${color}60`,
                color: color,
              }}
            >
              {badge}
            </span>
          )}
        </div>
        {subtitle && <p className="tooltip-subtitle">{subtitle}</p>}
      </div>

      <div className="tooltip-divider" />

      <div className="tooltip-metrics-grid">
        {metrics.map((item, idx) => (
          <div key={idx} className="tooltip-metric-item">
            <span className="tooltip-metric-label">{item.label}</span>
            <span className={`tooltip-metric-value ${item.highlight || 'neutral'}`}>
              {item.value}
            </span>
          </div>
        ))}
      </div>

      {footer && (
        <>
          <div className="tooltip-divider light" />
          <p className="tooltip-footer">{footer}</p>
        </>
      )}
    </div>
  )
}

export default PortfolioTooltip

