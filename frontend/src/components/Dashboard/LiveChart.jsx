/**
 * LiveChart — real-time area chart for one metric.
 *
 * Enhancements:
 * - Threshold reference line (dashed red at 85%)
 * - Loading skeleton while no data
 * - Custom tooltip with delta vs previous
 * - Gradient fill keyed to current value color
 * - isAnimationActive=false keeps the chart smooth under fast updates
 */
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { format } from 'date-fns'
import Skeleton from '../ui/Skeleton'

const TOOLTIP_STYLE = {
  contentStyle: {
    background: '#171d2d',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: '8px 12px',
    fontSize: 12,
  },
  labelStyle:   { color: '#6b7280', marginBottom: 4 },
  itemStyle:    { color: '#f3f4f6', fontFamily: 'JetBrains Mono, monospace' },
  cursor:       { stroke: 'rgba(255,255,255,0.08)', strokeWidth: 1 },
}

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null
  const val = payload[0]?.value ?? 0
  return (
    <div className="glass-card px-3 py-2.5 text-xs min-w-[100px]">
      <p className="text-gray-500 mb-1">{label}</p>
      <p className="font-mono font-bold text-white text-base">
        {val.toFixed(2)}<span className="text-gray-400 text-xs ml-0.5">{unit}</span>
      </p>
    </div>
  )
}

// Derive stroke color from the latest value
function getColor(latestValue, baseColor, unit) {
  if (unit !== '%') return baseColor
  if (latestValue >= 90) return '#ef4444'
  if (latestValue >= 75) return '#f59e0b'
  return baseColor
}

export default function LiveChart({
  title,
  data = [],
  dataKey,
  color     = '#6366f1',
  unit      = '%',
  height    = 190,
  threshold = unit === '%' ? 85 : null,
}) {
  const chartData = data.map(d => ({
    time:  d.created_at ? format(new Date(d.created_at), 'HH:mm:ss') : '',
    value: d[dataKey] ?? 0,
  }))

  const latest      = chartData.at(-1)?.value ?? 0
  const activeColor = getColor(latest, color, unit)
  const gradId      = `grad-${dataKey}`

  if (!chartData.length) {
    return <Skeleton.Chart height={height + 48} />
  }

  return (
    <div className="glass-card p-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300">{title}</h3>
        <div className="flex items-center gap-2">
          {threshold && latest >= threshold && (
            <span className="badge badge-danger text-[10px] py-0 animate-fade-in">High</span>
          )}
          <span
            className="font-mono text-lg font-bold tabular-nums transition-colors duration-300"
            style={{ color: activeColor }}
          >
            {latest.toFixed(1)}{unit}
          </span>
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={activeColor} stopOpacity={0.25} />
              <stop offset="100%" stopColor={activeColor} stopOpacity={0.0}  />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
            horizontal vertical={false}
          />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 9, fill: '#4b5563' }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={unit === '%' ? [0, 100] : ['auto', 'auto']}
            tick={{ fontSize: 9, fill: '#4b5563' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={v => `${v}${unit === '%' ? '' : ''}`}
          />

          {/* Threshold reference line */}
          {threshold && (
            <ReferenceLine
              y={threshold}
              stroke="rgba(239,68,68,0.4)"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
          )}

          <Tooltip content={<CustomTooltip unit={unit} />} {...TOOLTIP_STYLE} />

          <Area
            type="monotoneX"
            dataKey="value"
            stroke={activeColor}
            strokeWidth={2}
            fill={`url(#${gradId})`}
            dot={false}
            activeDot={{ r: 3, fill: activeColor, stroke: '#0d1117', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
