import { Fragment, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import AppLayout from '../components/AppLayout'
import {
  createAlert,
  deleteAlert,
  getAlertsBySymbol,
  updateAlert,
} from '../services/alert.service'
import type { AlertDetail, AlertLogic, Trigger } from '../types'
import './AlertsPage.css'

/** Editable draft of a single trigger condition (threshold kept as string). */
interface TriggerDraft {
  indicator: string
  operator: string
  threshold: string
}

const INDICATORS = [
  { value: 'PRICE', label: 'Price ($)' },
  { value: 'VOLUME', label: 'Volume' },
  { value: 'RSI', label: 'RSI' },
]

const OPERATORS = [
  { value: '>', label: '> Above' },
  { value: '<', label: '< Below' },
  { value: '==', label: '== Equal' },
  { value: '>=', label: '>= Above or equal' },
  { value: '<=', label: '<= Below or equal' },
  { value: '!=', label: '!= Not equal' },
]

const newTriggerDraft = (): TriggerDraft => ({
  indicator: 'PRICE',
  operator: '>',
  threshold: '150.00',
})

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlSymbol = (searchParams.get('symbol') || 'AAPL').toUpperCase()

  const [createSymbol, setCreateSymbol] = useState(urlSymbol)
  const [logic, setLogic] = useState<AlertLogic>('AND')
  const [triggers, setTriggers] = useState<TriggerDraft[]>([newTriggerDraft()])
  const [active, setActive] = useState(true)

  const [lookupSymbol, setLookupSymbol] = useState(urlSymbol)
  const [alerts, setAlerts] = useState<AlertDetail[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)
  const [editingAlertId, setEditingAlertId] = useState<string | number | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let isMounted = true

    async function loadAlerts() {
      if (!urlSymbol.trim()) {
        if (isMounted) setAlerts([])
        return
      }
      if (isMounted) setLoadingAlerts(true)
      try {
        const res = await getAlertsBySymbol(urlSymbol.trim())
        if (isMounted) setAlerts(Array.isArray(res.data) ? res.data : [])
      } catch (err) {
        console.warn('Unable to load alerts for symbol:', err)
        if (isMounted) setAlerts([])
      } finally {
        if (isMounted) setLoadingAlerts(false)
      }
    }

    loadAlerts()
    return () => {
      isMounted = false
    }
  }, [urlSymbol, reloadKey])

  const handleLookupSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (lookupSymbol) {
      setSearchParams({ symbol: lookupSymbol.toUpperCase() })
    }
  }

  const addTrigger = () => setTriggers((prev) => [...prev, newTriggerDraft()])

  const removeTrigger = (index: number) =>
    setTriggers((prev) =>
      prev.length <= 1 ? prev : prev.filter((_, i) => i !== index),
    )

  const updateTrigger = (index: number, patch: Partial<TriggerDraft>) =>
    setTriggers((prev) =>
      prev.map((t, i) => (i === index ? { ...t, ...patch } : t)),
    )

  /** Parse the draft rows into API triggers, or null when a threshold is invalid. */
  const buildTriggers = (): Trigger[] | null => {
    const result: Trigger[] = []
    for (let i = 0; i < triggers.length; i += 1) {
      const value = parseFloat(triggers[i].threshold)
      if (Number.isNaN(value)) return null
      result.push({
        indicator: triggers[i].indicator,
        operator: triggers[i].operator,
        threshold: value,
        position: i,
      })
    }
    return result
  }

  const resetForm = () => {
    setEditingAlertId(null)
    setFormError(null)
    setFormSuccess(null)
    setTriggers([newTriggerDraft()])
    setLogic('AND')
  }

  const handleCreateAlert = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError(null)
    setFormSuccess(null)

    const payloadTriggers = buildTriggers()
    if (!payloadTriggers || payloadTriggers.length === 0) {
      setFormError('Please enter a valid numeric threshold for every condition.')
      return
    }

    setSubmitting(true)
    try {
      if (editingAlertId !== null) {
        await updateAlert({
          id: String(editingAlertId),
          active,
          logic,
          triggers: payloadTriggers,
        })
      } else {
        await createAlert({
          symbol: createSymbol.trim().toUpperCase(),
          active,
          logic,
          triggers: payloadTriggers,
        })
      }

      setFormSuccess(
        editingAlertId !== null
          ? `Alert for ${createSymbol.toUpperCase()} updated successfully!`
          : `Alert for ${createSymbol.toUpperCase()} created successfully!`,
      )
      setEditingAlertId(null)

      // Refresh alerts view
      setLookupSymbol(createSymbol)
      setSearchParams({ symbol: createSymbol.toUpperCase() })
      setReloadKey((k) => k + 1)
    } catch (err) {
      console.error('Failed to save alert:', err)
      setFormError(err instanceof Error ? err.message : 'Failed to save alert.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteAlert = async (alertId: string | number) => {
    try {
      await deleteAlert(String(alertId))
      setReloadKey((k) => k + 1)
    } catch (err) {
      console.error('Failed to delete alert:', err)
      alert(err instanceof Error ? err.message : 'Failed to delete alert')
    }
  }

  const handleEditAlert = (alertItem: AlertDetail) => {
    setEditingAlertId(alertItem.id)
    setCreateSymbol(alertItem.symbol)
    setActive(alertItem.active !== false && alertItem.status !== false)
    setLogic((alertItem.logic || 'AND') as AlertLogic)
    if (alertItem.triggers && alertItem.triggers.length > 0) {
      const ordered = [...alertItem.triggers].sort(
        (a, b) => (a.position ?? 0) - (b.position ?? 0),
      )
      setTriggers(
        ordered.map((t) => ({
          indicator: t.indicator || 'PRICE',
          operator: t.operator || t.condition || '>',
          threshold: String(t.threshold ?? '0'),
        })),
      )
    } else {
      setTriggers([newTriggerDraft()])
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
              {editingAlertId !== null ? 'Edit Alert Rule' : 'Create Alert Rule'}
            </h2>

            {formError && <div className="alerts-banner error">{formError}</div>}

            {formSuccess && <div className="alerts-banner success">{formSuccess}</div>}

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
                <span>Combine conditions with</span>
                <div className="alerts-logic-toggle" role="group" aria-label="Condition logic">
                  <button
                    type="button"
                    className={`alerts-logic-btn ${logic === 'AND' ? 'active' : ''}`}
                    onClick={() => setLogic('AND')}
                    aria-pressed={logic === 'AND'}
                  >
                    AND (all match)
                  </button>
                  <button
                    type="button"
                    className={`alerts-logic-btn ${logic === 'OR' ? 'active' : ''}`}
                    onClick={() => setLogic('OR')}
                    aria-pressed={logic === 'OR'}
                  >
                    OR (any match)
                  </button>
                </div>
              </div>

              <div className="alerts-field">
                <span>Trigger Conditions</span>
                <div className="trigger-list">
                  {triggers.map((trigger, index) => (
                    <div className="trigger-row" key={index}>
                      <select
                        value={trigger.indicator}
                        onChange={(e) => updateTrigger(index, { indicator: e.target.value })}
                        aria-label={`Indicator ${index + 1}`}
                      >
                        {INDICATORS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>

                      <select
                        value={trigger.operator}
                        onChange={(e) => updateTrigger(index, { operator: e.target.value })}
                        aria-label={`Operator ${index + 1}`}
                      >
                        {OPERATORS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>

                      <input
                        type="number"
                        step="any"
                        value={trigger.threshold}
                        onChange={(e) => updateTrigger(index, { threshold: e.target.value })}
                        placeholder="Threshold"
                        required
                        aria-label={`Threshold ${index + 1}`}
                      />

                      <button
                        type="button"
                        className="trigger-remove-btn"
                        onClick={() => removeTrigger(index)}
                        disabled={triggers.length <= 1}
                        title="Remove condition"
                        aria-label={`Remove condition ${index + 1}`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <button type="button" className="alert-add-condition-btn" onClick={addTrigger}>
                  + Add condition
                </button>
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
                  : editingAlertId !== null
                  ? 'Save Changes'
                  : 'Create Alert Rule'}
              </button>

              {editingAlertId !== null && (
                <button type="button" className="alert-action-btn" onClick={resetForm}>
                  Cancel Edit
                </button>
              )}
            </form>
          </div>

          {/* Alert Lookup & Active Alerts */}
          <div className="alerts-card">
            <div className="alerts-list-header">
              <h2 className="alerts-card-title" style={{ margin: 0 }}>
                Alerts for Symbol
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
            ) : alerts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#abb5cb' }}>
                <p style={{ fontSize: '16px', color: '#f4f7ff', marginBottom: '6px' }}>
                  No alert found for {lookupSymbol || 'this symbol'}
                </p>
                <p style={{ fontSize: '13px' }}>
                  Use the form on the left to configure a notification trigger.
                </p>
              </div>
            ) : (
              <div>
                {alerts.map((alertItem) => {
                  const isActive =
                    alertItem.active !== false && alertItem.status !== false
                  return (
                    <div className="alert-item-card" key={String(alertItem.id)}>
                      <div className="alert-item-top">
                        <span className="alert-symbol-tag">
                          <Link
                            to={`/stock/${encodeURIComponent(alertItem.symbol)}`}
                            style={{ color: '#ffffff', textDecoration: 'none' }}
                          >
                            {alertItem.symbol}
                          </Link>
                        </span>
                        <span className={`alert-status-badge ${isActive ? 'active' : 'inactive'}`}>
                          {isActive ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                      </div>

                      <div className="alert-trigger-info">
                        <span>⚡</span>
                        {alertItem.triggers && alertItem.triggers.length > 0 ? (
                          alertItem.triggers.map((t, idx) => (
                            <Fragment key={idx}>
                              {idx > 0 && (
                                <span className="alert-trigger-joiner">
                                  {alertItem.logic || 'AND'}
                                </span>
                              )}
                              <span>
                                {t.indicator || 'PRICE'} {t.operator || t.condition || '>'} $
                                {t.threshold}
                              </span>
                            </Fragment>
                          ))
                        ) : (
                          <span>Price Condition Alert</span>
                        )}
                      </div>

                      <div className="alert-item-actions">
                        <span>ID: #{alertItem.id}</span>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            type="button"
                            className="alert-action-btn"
                            onClick={() => handleEditAlert(alertItem)}
                          >
                            Edit Rule
                          </button>
                          <button
                            type="button"
                            className="alert-action-btn delete"
                            onClick={() => handleDeleteAlert(alertItem.id)}
                          >
                            Delete Alert
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
