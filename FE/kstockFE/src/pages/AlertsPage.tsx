import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import { createAlert, deleteAlert, getAlertsBySymbol } from '../services/alert.service'
import type { AlertDetail } from '../types'
import './AlertsPage.css'

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSymbol = (searchParams.get('symbol') || 'AAPL').toUpperCase()

  const [createSymbol, setCreateSymbol] = useState(urlSymbol)
  const [indicator, setIndicator] = useState('PRICE')
  const [operator, setOperator] = useState('>')
  const [threshold, setThreshold] = useState<string>('150.00')
  const [active, setActive] = useState(true)

  const [lookupSymbol, setLookupSymbol] = useState(urlSymbol)
  const [alertData, setAlertData] = useState<AlertDetail | null>(null)
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)
  const [editingAlertId, setEditingAlertId] = useState<string | number | null>(null)

  useEffect(() => {
    let isMounted = true

    async function loadAlerts() {
      if (!urlSymbol.trim()) {
        if (isMounted) setAlertData(null)
        return
      }
      if (isMounted) setLoadingAlerts(true)
      try {
        const res = await getAlertsBySymbol(urlSymbol.trim())
        if (isMounted) setAlertData(res.data)
      } catch (err) {
        console.warn('Unable to load alerts for symbol:', err)
        if (isMounted) setAlertData(null)
      } finally {
        if (isMounted) setLoadingAlerts(false)
      }
    }

    loadAlerts()
    return () => {
      isMounted = false
    }
  }, [urlSymbol])

  const handleLookupSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (lookupSymbol) {
      setSearchParams({ symbol: lookupSymbol.toUpperCase() })
    }
  }

  const handleCreateAlert = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError(null)
    setFormSuccess(null)

    const numericThreshold = parseFloat(threshold)
    if (Number.isNaN(numericThreshold)) {
      setFormError('Please enter a valid numeric threshold.')
      return
    }

    setSubmitting(true)
    try {
      // If editing via delete-and-recreate workflow
      if (editingAlertId) {
        try {
          await deleteAlert(String(editingAlertId))
        } catch (delErr) {
          console.warn('Could not delete prior alert during recreate:', delErr)
        }
      }

      await createAlert({
        symbol: createSymbol.trim().toUpperCase(),
        active,
        triggers: [
          {
            indicator,
            operator,
            threshold: numericThreshold,
          },
        ],
      })

      setFormSuccess(
        editingAlertId
          ? `Alert for ${createSymbol.toUpperCase()} updated successfully!`
          : `Alert for ${createSymbol.toUpperCase()} created successfully!`,
      )
      setEditingAlertId(null)

      // Refresh alerts view
      setLookupSymbol(createSymbol)
      setSearchParams({ symbol: createSymbol.toUpperCase() })
    } catch (err) {
      console.error('Failed to create alert:', err)
      setFormError(err instanceof Error ? err.message : 'Failed to create alert.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteAlert = async (alertId: string | number) => {
    try {
      await deleteAlert(String(alertId))
      setAlertData(null)
    } catch (err) {
      console.error('Failed to delete alert:', err)
      alert(err instanceof Error ? err.message : 'Failed to delete alert')
    }
  }

  const handleEditAlert = (alertItem: AlertDetail) => {
    setEditingAlertId(alertItem.id)
    setCreateSymbol(alertItem.symbol)
    setActive(alertItem.active !== false && alertItem.status !== false)
    if (alertItem.triggers && alertItem.triggers.length > 0) {
      const firstTrigger = alertItem.triggers[0]
      setIndicator(firstTrigger.indicator || 'PRICE')
      setOperator(firstTrigger.operator || firstTrigger.condition || '>')
      setThreshold(String(firstTrigger.threshold ?? '0'))
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <AppLayout>
      <div className="alerts-page">
        <header className="alerts-header">
          <p className="alerts-kicker">Automation & Signals</p>
          <h1>Price & Indicator Alerts</h1>
        </header>

        <div className="alerts-grid">
          {/* Create Alert Form */}
          <div className="alerts-card">
            <h2 className="alerts-card-title">
              {editingAlertId ? 'Edit Alert (Delete & Recreate)' : 'Create Alert Rule'}
            </h2>

            {formError && (
              <div style={{ padding: '10px 14px', background: 'rgba(239, 83, 80, 0.15)', border: '1px solid rgba(239, 83, 80, 0.4)', borderRadius: '8px', color: '#ff8a9a', fontSize: '13px', marginBottom: '14px' }}>
                {formError}
              </div>
            )}

            {formSuccess && (
              <div style={{ padding: '10px 14px', background: 'rgba(52, 194, 147, 0.15)', border: '1px solid rgba(52, 194, 147, 0.4)', borderRadius: '8px', color: '#68e6c0', fontSize: '13px', marginBottom: '14px' }}>
                {formSuccess}
              </div>
            )}

            <form className="alerts-form" onSubmit={handleCreateAlert}>
              <label className="alerts-field">
                <span>Stock Symbol</span>
                <input
                  type="text"
                  placeholder="e.g. AAPL, IBM, TSLA"
                  value={createSymbol}
                  onChange={(e) => setCreateSymbol(e.target.value.toUpperCase())}
                  required
                />
              </label>

              <div className="alerts-field">
                <span>Trigger Condition</span>
                <div className="trigger-row">
                  <select
                    value={indicator}
                    onChange={(e) => setIndicator(e.target.value)}
                    aria-label="Indicator"
                  >
                    <option value="PRICE">Price ($)</option>
                    <option value="VOLUME">Volume</option>
                    <option value="RSI">RSI</option>
                  </select>

                  <select
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                    aria-label="Condition Operator"
                  >
                    <option value=">">&gt; Above</option>
                    <option value="<">&lt; Below</option>
                    <option value="==">== Equal</option>
                    <option value=">=">&gt;= Above or equal</option>
                    <option value="<=">&lt;= Below or equal</option>
                  </select>

                  <input
                    type="number"
                    step="any"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    placeholder="Threshold"
                    required
                    aria-label="Threshold value"
                  />
                </div>
              </div>

              <label className="alerts-checkbox-label">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                />
                <span>Enable alert immediately</span>
              </label>

              <button
                type="submit"
                className="alerts-submit-btn"
                disabled={submitting || !createSymbol.trim()}
              >
                {submitting
                  ? 'Saving alert...'
                  : editingAlertId
                  ? 'Save Changes'
                  : 'Create Alert Rule'}
              </button>

              {editingAlertId && (
                <button
                  type="button"
                  className="alert-action-btn"
                  onClick={() => {
                    setEditingAlertId(null)
                    setFormSuccess(null)
                  }}
                >
                  Cancel Edit
                </button>
              )}
            </form>
          </div>

          {/* Alert Lookup & Active Alerts */}
          <div className="alerts-card">
            <div className="alerts-list-header">
              <h2 className="alerts-card-title" style={{ margin: 0 }}>
                Active Alerts for Symbol
              </h2>
              <form onSubmit={handleLookupSubmit} style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="search"
                  className="alerts-lookup-input"
                  placeholder="Lookup symbol..."
                  value={lookupSymbol}
                  onChange={(e) => setLookupSymbol(e.target.value.toUpperCase())}
                />
                <button type="submit" className="alert-action-btn">
                  Search
                </button>
              </form>
            </div>

            {loadingAlerts ? (
              <p style={{ color: '#abb5cb', textAlign: 'center', padding: '30px 0' }}>
                Checking alerts for {lookupSymbol}...
              </p>
            ) : !alertData ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#abb5cb' }}>
                <p style={{ fontSize: '16px', color: '#f4f7ff', marginBottom: '6px' }}>
                  No active alert found for {lookupSymbol || 'this symbol'}
                </p>
                <p style={{ fontSize: '13px' }}>
                  Use the form on the left to configure a notification trigger.
                </p>
              </div>
            ) : (
              <div>
                <div className="alert-item-card">
                  <div className="alert-item-top">
                    <span className="alert-symbol-tag">
                      <Link
                        to={`/stock/${encodeURIComponent(alertData.symbol)}`}
                        style={{ color: '#ffffff', textDecoration: 'none' }}
                      >
                        {alertData.symbol}
                      </Link>
                    </span>
                    <span
                      className={`alert-status-badge ${
                        alertData.active !== false && alertData.status !== false
                          ? 'active'
                          : 'inactive'
                      }`}
                    >
                      {alertData.active !== false && alertData.status !== false
                        ? 'ACTIVE'
                        : 'INACTIVE'}
                    </span>
                  </div>

                  <div className="alert-trigger-info">
                    <span>⚡</span>
                    {alertData.triggers && alertData.triggers.length > 0 ? (
                      alertData.triggers.map((t, idx) => (
                        <span key={idx}>
                          {t.indicator || 'PRICE'} {t.operator || t.condition || '>'} ${t.threshold}
                        </span>
                      ))
                    ) : (
                      <span>Price Condition Alert</span>
                    )}
                  </div>

                  <div className="alert-item-actions">
                    <span>ID: #{alertData.id}</span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        className="alert-action-btn"
                        onClick={() => handleEditAlert(alertData)}
                      >
                        Edit Rule
                      </button>
                      <button
                        type="button"
                        className="alert-action-btn delete"
                        onClick={() => handleDeleteAlert(alertData.id)}
                      >
                        Delete Alert
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  )
}

