/**
 * AlertsPanel — live alert feed for the Dashboard.
 *
 * Enhancements:
 * - Auto-reloads when alertCount changes (new WS alert arrives)
 * - Animated entry for new alerts
 * - Empty state with icon
 */
import { useState, useEffect, useRef } from 'react'
import { AlertTriangle, X, CheckCheck, ShieldCheck } from 'lucide-react'
import { getAlerts, updateAlert, markAllAlertsRead } from '../../services/api'
import { useMetrics } from '../../context/MetricsContext'
import { formatDistanceToNow } from 'date-fns'

function AlertRow({ alert, onDismiss }) {
  const isCritical = alert.severity === 'critical'
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border transition-all duration-200 animate-slide-up
      ${isCritical ? 'bg-red-500/8 border-red-500/20' : 'bg-amber-500/8 border-amber-500/20'}`}
    >
      <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0
        ${isCritical ? 'text-red-400' : 'text-amber-400'}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className={isCritical ? 'badge badge-danger text-[10px]' : 'badge badge-warning text-[10px]'}>
            {alert.severity}
          </span>
          {!alert.is_read && (
            <span className="badge badge-info text-[10px]">new</span>
          )}
        </div>
        <p className="text-xs font-medium text-white leading-snug">{alert.message}</p>
        <p className="text-[10px] text-gray-500 mt-0.5">
          {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
        </p>
      </div>
      <button
        onClick={() => onDismiss(alert.id)}
        className="text-gray-600 hover:text-gray-300 transition-colors flex-shrink-0 mt-0.5"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  )
}

export default function AlertsPanel({ limit = 6 }) {
  const [alerts, setAlerts]   = useState([])
  const { refreshCounts, alertCount } = useMetrics()
  const prevCount = useRef(alertCount)

  const load = async () => {
    try {
      const res = await getAlerts()
      setAlerts(res.data.slice(0, limit))
    } catch {}
  }

  // Initial load
  useEffect(() => { load() }, [])

  // Reload when new alert arrives via WebSocket (alertCount bumped)
  useEffect(() => {
    if (alertCount > prevCount.current) load()
    prevCount.current = alertCount
  }, [alertCount])

  const dismiss = async (id) => {
    await updateAlert(id, { is_read: true, is_resolved: true })
    setAlerts(prev => prev.filter(a => a.id !== id))
    refreshCounts()
  }

  const markAll = async () => {
    await markAllAlertsRead()
    setAlerts(prev => prev.map(a => ({ ...a, is_read: true })))
    refreshCounts()
  }

  return (
    <div className="glass-card flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <p className="text-sm font-semibold text-gray-200">Alerts</p>
          {alerts.filter(a => !a.is_read).length > 0 && (
            <span className="badge badge-danger text-[10px]">
              {alerts.filter(a => !a.is_read).length} new
            </span>
          )}
        </div>
        {alerts.length > 0 && (
          <button
            onClick={markAll}
            className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
          >
            <CheckCheck className="w-3 h-3" />
            Mark all read
          </button>
        )}
      </div>

      {/* Body */}
      <div className="p-3 space-y-2 overflow-y-auto max-h-72 no-scrollbar">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <ShieldCheck className="w-8 h-8 text-green-500/40 mb-2" />
            <p className="text-xs text-gray-500">All systems normal</p>
          </div>
        ) : (
          alerts.map(a => <AlertRow key={a.id} alert={a} onDismiss={dismiss} />)
        )}
      </div>
    </div>
  )
}
