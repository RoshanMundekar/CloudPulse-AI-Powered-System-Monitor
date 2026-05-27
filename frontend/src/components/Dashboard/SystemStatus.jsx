/**
 * SystemStatus — compact bar showing hostname, platform, uptime,
 * and current WebSocket connection state.
 */
import { Monitor, Server, Clock, Wifi } from 'lucide-react'
import { useMetrics } from '../../context/MetricsContext'
import { useEffect, useState } from 'react'

export default function SystemStatus() {
  const { current, wsStatus } = useMetrics()
  const [uptime, setUptime] = useState(0)

  // Track seconds since page load as a proxy for monitoring uptime
  useEffect(() => {
    const start = Date.now()
    const t = setInterval(() => setUptime(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(t)
  }, [])

  const fmtUptime = s => {
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    if (h > 0) return `${h}h ${m}m`
    if (m > 0) return `${m}m ${sec}s`
    return `${sec}s`
  }

  const stats = [
    { icon: Server,  label: 'Host',     value: current.hostname  || 'N/A' },
    { icon: Monitor, label: 'Platform', value: current.platform  || 'N/A' },
    { icon: Wifi,    label: 'Status',
      value: wsStatus,
      valueClass: wsStatus === 'connected' ? 'text-green-400' : 'text-red-400',
    },
    { icon: Clock,   label: 'Uptime',   value: fmtUptime(uptime), mono: true },
  ]

  return (
    <div className="glass-card px-5 py-3 flex items-center gap-6 flex-wrap animate-fade-in">
      {stats.map(({ icon: Icon, label, value, valueClass = 'text-gray-200', mono }) => (
        <div key={label} className="flex items-center gap-2">
          <Icon className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
          <span className="text-xs text-gray-500">{label}:</span>
          <span className={`text-xs font-medium truncate max-w-[120px]
                           ${valueClass} ${mono ? 'font-mono tabular-nums' : ''}`}>
            {value}
          </span>
        </div>
      ))}
    </div>
  )
}
