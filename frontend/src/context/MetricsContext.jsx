/**
 * MetricsContext — global real-time state.
 *
 * Improvements over original:
 * 1. Loads initial history + latest metric from REST on mount (charts aren't
 *    empty while waiting for the first WebSocket message).
 * 2. Toast queue: new alerts/anomalies received over WebSocket queue a
 *    notification; components consume it via addToast / toasts.
 * 3. Tracks lastUpdated timestamp so the header can show "X seconds ago".
 */
import {
  createContext, useContext, useState,
  useCallback, useEffect, useRef,
} from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import {
  getAlertCount, getAnomalyCount,
  getLatestMetric, getMetricHistory,
} from '../services/api'

const MetricsContext = createContext(null)
const MAX_HISTORY = 60

const EMPTY_METRIC = {
  cpu_percent: 0, ram_percent: 0, disk_percent: 0,
  net_bytes_recv_mb: 0, net_bytes_sent_mb: 0,
  disk_read_mb: 0, disk_write_mb: 0,
  top_processes: [], created_at: null,
}

let toastIdCounter = 0

export function MetricsProvider({ children }) {
  const [current,        setCurrent]        = useState(EMPTY_METRIC)
  const [history,        setHistory]        = useState([])
  const [wsStatus,       setWsStatus]       = useState('connecting')
  const [alertCount,     setAlertCount]     = useState(0)
  const [anomalyCount,   setAnomalyCount]   = useState(0)
  const [recentAnomalies, setRecentAnomalies] = useState([])
  const [toasts,         setToasts]         = useState([])
  const [lastUpdated,    setLastUpdated]     = useState(null)
  const [initialized,    setInitialized]     = useState(false)

  // ── Toast helpers ────────────────────────────────────────────────────────
  const addToast = useCallback((type, title, message, duration = 5000) => {
    const id = ++toastIdCounter
    setToasts(prev => [...prev.slice(-4), { id, type, title, message }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  // ── Count refresh ─────────────────────────────────────────────────────────
  const refreshCounts = useCallback(async () => {
    try {
      const [a, an] = await Promise.all([getAlertCount(), getAnomalyCount()])
      setAlertCount(a.data.unread_count ?? 0)
      setAnomalyCount(an.data.count    ?? 0)
    } catch {}
  }, [])

  // ── Bootstrap: load latest + 1h history from REST on mount ───────────────
  useEffect(() => {
    let cancelled = false
    async function bootstrap() {
      try {
        const [latest, hist] = await Promise.all([
          getLatestMetric(),
          getMetricHistory(1),
        ])
        if (cancelled) return
        if (latest.data && Object.keys(latest.data).length) {
          setCurrent(prev => ({ ...prev, ...latest.data }))
          setLastUpdated(new Date())
        }
        if (hist.data?.length) {
          setHistory(hist.data.map(d => ({ ...d, time: d.created_at })))
        }
      } catch {}
      refreshCounts()
      if (!cancelled) setInitialized(true)
    }
    bootstrap()
    return () => { cancelled = true }
  }, [refreshCounts])

  // ── WebSocket handlers ────────────────────────────────────────────────────
  const handlers = {
    onOpen:  () => { setWsStatus('connected'); refreshCounts() },
    onClose: () => setWsStatus('disconnected'),
    onError: () => setWsStatus('error'),

    onMetric: useCallback((data) => {
      setCurrent(data)
      setLastUpdated(new Date())
      setHistory(prev => {
        const next = [...prev, { ...data, time: data.created_at }]
        return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
      })
    }, []),

    onAnomaly: useCallback((data) => {
      setRecentAnomalies(prev => [data, ...prev].slice(0, 10))
      setAnomalyCount(c => c + 1)
      addToast('danger', 'Anomaly Detected',
        data.description || `Score: ${data.score?.toFixed(3)} · ${data.severity}`)
    }, [addToast]),
  }

  // Broadcast alert toasts when the WS metric message includes new alerts
  const prevAlertCount = useRef(0)
  useEffect(() => {
    if (alertCount > prevAlertCount.current && initialized) {
      addToast('warning', 'New Alert', `${alertCount} unread alert${alertCount !== 1 ? 's' : ''}`)
    }
    prevAlertCount.current = alertCount
  }, [alertCount, initialized, addToast])

  useWebSocket(handlers)

  return (
    <MetricsContext.Provider value={{
      current, history, wsStatus,
      alertCount, anomalyCount, recentAnomalies,
      toasts, addToast, removeToast,
      lastUpdated, initialized,
      refreshCounts,
    }}>
      {children}
    </MetricsContext.Provider>
  )
}

export const useMetrics = () => {
  const ctx = useContext(MetricsContext)
  if (!ctx) throw new Error('useMetrics must be inside MetricsProvider')
  return ctx
}
