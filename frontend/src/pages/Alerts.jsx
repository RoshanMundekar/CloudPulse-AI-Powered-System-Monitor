/**
 * Alerts page — full alert management with live count badges per filter.
 *
 * Enhancements:
 * - Per-filter count badges (All 12 · Unread 3 · Critical 1)
 * - Live reload when alertCount changes in context
 * - Animated entry for new rows
 * - Skeleton loading state
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react'
import { getAlerts, updateAlert, markAllAlertsRead } from '../services/api'
import { useMetrics } from '../context/MetricsContext'
import { formatDistanceToNow, format } from 'date-fns'
import Header   from '../components/Layout/Header'
import Skeleton from '../components/ui/Skeleton'

const FILTERS = ['all', 'unread', 'active', 'critical']

function FilterTab({ value, current, count, onClick }) {
  const active = value === current
  return (
    <button
      onClick={() => onClick(value)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                  capitalize transition-all
                  ${active ? 'bg-brand-primary text-white' : 'glass-card text-gray-400 hover:text-white'}`}
    >
      {value}
      {count > 0 && (
        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold
          ${active ? 'bg-white/20 text-white' : 'bg-white/10 text-gray-400'}`}>
          {count}
        </span>
      )}
    </button>
  )
}

export default function Alerts() {
  const [alerts,  setAlerts]  = useState([])
  const [filter,  setFilter]  = useState('all')
  const [loading, setLoading] = useState(true)
  const { refreshCounts, alertCount } = useMetrics()
  const prevCount = useRef(alertCount)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getAlerts()
      setAlerts(res.data)
    } catch {}
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // Auto-reload when new alerts arrive over WebSocket
  useEffect(() => {
    if (alertCount > prevCount.current) load()
    prevCount.current = alertCount
  }, [alertCount, load])

  const resolve = async (id) => {
    await updateAlert(id, { is_read: true, is_resolved: true })
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_resolved: true, is_read: true } : a))
    refreshCounts()
  }

  const markAll = async () => {
    await markAllAlertsRead()
    setAlerts(prev => prev.map(a => ({ ...a, is_read: true })))
    refreshCounts()
  }

  // Per-filter counts
  const counts = {
    all:      alerts.length,
    unread:   alerts.filter(a => !a.is_read).length,
    active:   alerts.filter(a => !a.is_resolved).length,
    critical: alerts.filter(a => a.severity === 'critical').length,
  }

  const filtered = alerts.filter(a => {
    if (filter === 'unread')   return !a.is_read
    if (filter === 'active')   return !a.is_resolved
    if (filter === 'critical') return a.severity === 'critical'
    return true
  })

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header title="Alerts" onRefresh={load} />
      <main className="flex-1 overflow-y-auto p-5 space-y-4">

        {/* Filter + actions bar */}
        <div className="flex items-center gap-2 flex-wrap">
          {FILTERS.map(f => (
            <FilterTab key={f} value={f} current={filter} count={counts[f]} onClick={setFilter} />
          ))}
          <div className="ml-auto flex items-center gap-2">
            <button onClick={markAll} className="btn-ghost text-xs py-1.5">
              Mark all read
            </button>
          </div>
        </div>

        {/* Alert list */}
        {loading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => <Skeleton.Row key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass-card p-14 text-center animate-fade-in">
            <ShieldCheck className="w-12 h-12 text-green-500/30 mx-auto mb-3" />
            <p className="text-gray-400 text-sm font-medium">No alerts in this view</p>
            <p className="text-gray-600 text-xs mt-1">
              {filter !== 'all' ? 'Try switching to "all"' : 'System is running normally'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map(alert => (
              <div
                key={alert.id}
                className={`glass-card p-4 flex items-start gap-4 transition-all duration-200 animate-fade-in
                  ${alert.is_resolved ? 'opacity-40' : ''}
                  ${!alert.is_read    ? 'border-l-2 border-l-amber-500/50' : ''}`}
              >
                <AlertTriangle className={`w-4 h-4 mt-0.5 flex-shrink-0
                  ${alert.severity === 'critical' ? 'text-red-400' : 'text-amber-400'}`} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className={alert.severity === 'critical' ? 'badge badge-danger' : 'badge badge-warning'}>
                      {alert.severity}
                    </span>
                    {!alert.is_read && <span className="badge badge-info">new</span>}
                    {alert.is_resolved && <span className="badge badge-ghost">resolved</span>}
                    <span className="text-[10px] text-gray-600 font-mono">
                      {alert.metric_value?.toFixed(1)}% &gt; {alert.threshold_value}%
                    </span>
                  </div>
                  <p className="text-sm text-white font-medium leading-snug">{alert.message}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {format(new Date(alert.created_at), 'PPpp')}
                    <span className="mx-1.5 text-gray-700">·</span>
                    {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                  </p>
                </div>

                {!alert.is_resolved && (
                  <button
                    onClick={() => resolve(alert.id)}
                    className="flex-shrink-0 flex items-center gap-1 text-xs text-gray-500
                               hover:text-green-400 transition-colors"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Resolve</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

      </main>
    </div>
  )
}
