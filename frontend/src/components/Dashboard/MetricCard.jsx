/**
 * MetricCard — animated progress ring + mini sparkline trend.
 *
 * Enhancements:
 * - Mini SVG sparkline shows last N history points as a trend line
 * - Trend arrow indicates direction vs previous reading
 * - Ring pulses red when value is critical (≥90%)
 * - Value text animates on change via CSS key
 */
import { useMemo, useRef } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

// Tiny sparkline rendered as a pure SVG polyline — no Recharts needed
function MiniSparkline({ data, dataKey, color }) {
  if (!data?.length) return null
  const W = 72, H = 28
  const values = data.slice(-20).map(d => d[dataKey] ?? 0)
  if (values.length < 2) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W
    const y = H - ((v - min) / range) * (H - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  return (
    <svg width={W} height={H} className="overflow-visible opacity-70">
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// Determine ring stroke color by threshold
function ringColor(pct) {
  if (pct >= 90) return '#ef4444'
  if (pct >= 75) return '#f59e0b'
  if (pct >= 50) return '#eab308'
  return '#6366f1'
}

function valueColor(pct) {
  if (pct >= 90) return 'text-red-400'
  if (pct >= 75) return 'text-amber-400'
  return 'text-white'
}

export default function MetricCard({
  title,
  value,
  unit = '%',
  icon: Icon,
  subtitle,
  history = [],
  dataKey,
  sparkColor = '#6366f1',
}) {
  const pct = Math.min(100, Math.max(0, parseFloat(value) || 0))
  const isCritical = pct >= 90

  // Trend: compare last 5 vs previous 5 readings
  const trend = useMemo(() => {
    if (!history || history.length < 10 || !dataKey) return 'stable'
    const recent = history.slice(-5).map(d => d[dataKey] ?? 0)
    const older  = history.slice(-10, -5).map(d => d[dataKey] ?? 0)
    const avg = arr => arr.reduce((a, b) => a + b, 0) / arr.length
    const diff = avg(recent) - avg(older)
    if (diff >  1.5) return 'up'
    if (diff < -1.5) return 'down'
    return 'stable'
  }, [history, dataKey])

  // SVG ring
  const r           = 34
  const circumference = 2 * Math.PI * r
  const offset      = circumference - (pct / 100) * circumference
  const color       = ringColor(pct)

  return (
    <div className={`glass-card p-4 flex items-center gap-4 transition-all duration-200
                     hover:border-white/10 animate-fade-in
                     ${isCritical ? 'border-red-500/30 shadow-glow-red' : ''}`}>

      {/* Progress ring */}
      <div className={`relative flex-shrink-0 ${isCritical ? 'animate-ring-pulse' : ''}`}>
        <svg width="80" height="80" viewBox="0 0 80 80">
          {/* Track */}
          <circle cx="40" cy="40" r={r} fill="none"
            stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
          {/* Filled arc */}
          <circle cx="40" cy="40" r={r} fill="none"
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 40 40)"
            style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.4s ease' }}
          />
        </svg>
        {Icon && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Icon className="w-4 h-4 text-gray-400" />
          </div>
        )}
      </div>

      {/* Text + sparkline */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <p className="text-xs text-gray-400 font-medium truncate">{title}</p>
          {trend === 'up'   && <TrendingUp   className="w-3 h-3 text-red-400 flex-shrink-0" />}
          {trend === 'down' && <TrendingDown  className="w-3 h-3 text-green-400 flex-shrink-0" />}
          {trend === 'stable' && <Minus       className="w-3 h-3 text-gray-600 flex-shrink-0" />}
        </div>

        <p className={`metric-value-sm ${valueColor(pct)} animate-count-up`} key={pct.toFixed(0)}>
          {unit === '%' ? `${pct.toFixed(1)}%` : `${Number(value).toFixed(1)} ${unit}`}
        </p>

        {subtitle && (
          <p className="text-[10px] text-gray-500 mt-0.5 truncate font-mono">{subtitle}</p>
        )}

        {/* Mini sparkline */}
        {dataKey && history.length > 1 && (
          <div className="mt-2">
            <MiniSparkline data={history} dataKey={dataKey} color={color} />
          </div>
        )}
      </div>
    </div>
  )
}
