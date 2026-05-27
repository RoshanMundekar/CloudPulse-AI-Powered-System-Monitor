import { useEffect, useState } from 'react'
import { BellRing, RefreshCw } from 'lucide-react'
import { useMetrics } from '../../context/MetricsContext'
import { formatDistanceToNow } from 'date-fns'

export default function Header({ title, onRefresh }) {
  const { wsStatus, alertCount, lastUpdated, refreshCounts } = useMetrics()
  const [now, setNow] = useState(new Date())

  // Tick clock every second for the "X seconds ago" display
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const ago = lastUpdated
    ? formatDistanceToNow(lastUpdated, { addSuffix: true, includeSeconds: true })
    : 'waiting for data…'

  const handleRefresh = async () => {
    await refreshCounts()
    onRefresh?.()
  }

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-white/[0.06] bg-dark-200/60 backdrop-blur-md flex-shrink-0">
      {/* Title */}
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold text-white">{title}</h1>
        {wsStatus === 'connected' && (
          <span className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-green-500/10 border border-green-500/20">
            <span className="live-dot w-1.5 h-1.5" />
            <span className="text-[10px] font-bold text-green-400 uppercase tracking-wider">Live</span>
          </span>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Last updated */}
        <p className="hidden md:block text-xs text-gray-500 tabular-nums">
          Updated {ago}
        </p>

        {/* Refresh */}
        <button
          onClick={handleRefresh}
          className="btn-ghost p-2 rounded-lg"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* Alert bell */}
        <button className="relative btn-ghost p-2 rounded-lg" title="Alerts">
          <BellRing className="w-3.5 h-3.5" />
          {alertCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full
                             bg-red-500 text-white text-[9px] font-bold
                             flex items-center justify-center animate-bounce-in">
              {alertCount > 9 ? '9+' : alertCount}
            </span>
          )}
        </button>

        {/* Clock */}
        <div className="hidden sm:block text-xs font-mono text-gray-500 tabular-nums w-16 text-right">
          {now.toLocaleTimeString('en-IN', { hour12: false })}
        </div>
      </div>
    </header>
  )
}
