/**
 * AnomalyFeed — live feed of AI-detected anomalies.
 * Combines WebSocket real-time events with initial REST load.
 */
import { useState, useEffect } from 'react'
import { Zap, CheckCircle2 } from 'lucide-react'
import { getAnomalies, resolveAnomaly } from '../../services/api'
import { useMetrics } from '../../context/MetricsContext'
import { formatDistanceToNow } from 'date-fns'

const SEVERITY_STYLES = {
  critical: 'bg-red-500/10 border-red-500/25 text-red-400',
  high:     'bg-orange-500/10 border-orange-500/25 text-orange-400',
  medium:   'bg-amber-500/10 border-amber-500/25 text-amber-400',
  low:      'bg-yellow-500/10 border-yellow-500/25 text-yellow-400',
}

export default function AnomalyFeed({ limit = 6 }) {
  const [anomalies, setAnomalies] = useState([])
  const { recentAnomalies }       = useMetrics()

  useEffect(() => {
    getAnomalies(24).then(res => setAnomalies(res.data.slice(0, limit))).catch(() => {})
  }, [])

  // Prepend real-time anomalies from WebSocket
  useEffect(() => {
    if (!recentAnomalies.length) return
    setAnomalies(prev => {
      const ids = new Set(prev.map(a => a.id))
      const fresh = recentAnomalies.filter(a => !ids.has(a.id))
      return [...fresh, ...prev].slice(0, limit)
    })
  }, [recentAnomalies, limit])

  const resolve = async (id) => {
    await resolveAnomaly(id)
    setAnomalies(prev => prev.map(a => a.id === id ? { ...a, is_resolved: true } : a))
  }

  return (
    <div className="glass-card flex flex-col">
      <div className="flex items-center gap-2 px-5 py-3.5 border-b border-white/[0.06]">
        <Zap className="w-3.5 h-3.5 text-indigo-400" />
        <p className="text-sm font-semibold text-gray-200">AI Anomaly Feed</p>
        <span className="text-[10px] text-gray-500 ml-auto">Isolation Forest</span>
      </div>

      <div className="p-3 space-y-2 overflow-y-auto max-h-72 no-scrollbar">
        {anomalies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8">
            <CheckCircle2 className="w-8 h-8 text-green-500/30 mb-2" />
            <p className="text-xs text-gray-500">No anomalies detected</p>
          </div>
        ) : (
          anomalies.map(a => (
            <div
              key={a.id}
              className={`p-3 rounded-lg border text-xs transition-all animate-slide-up
                          ${SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.low}
                          ${a.is_resolved ? 'opacity-40' : ''}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="font-bold uppercase tracking-wide text-[10px]">
                      {a.severity}
                    </span>
                    <span className="text-gray-500">·</span>
                    <span className="font-mono text-[10px]">score {a.anomaly_score?.toFixed(3)}</span>
                  </div>
                  <p className="leading-snug opacity-90 line-clamp-2">{a.description}</p>
                  <p className="text-[10px] opacity-50 mt-1">
                    {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                  </p>
                </div>
                {!a.is_resolved && (
                  <button
                    onClick={() => resolve(a.id)}
                    className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
