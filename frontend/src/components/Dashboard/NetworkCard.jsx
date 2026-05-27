/**
 * NetworkCard — dual in/out bandwidth display with a split area chart.
 */
import {
  AreaChart, Area, XAxis, YAxis,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { format } from 'date-fns'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card px-3 py-2 text-xs space-y-1">
      <p className="text-gray-500">{label}</p>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-gray-300">{p.name}:</span>
          <span className="font-mono font-bold text-white">{(p.value || 0).toFixed(2)} MB</span>
        </div>
      ))}
    </div>
  )
}

export default function NetworkCard({ history = [], current = {} }) {
  const chartData = history.slice(-40).map(d => ({
    time: d.created_at ? format(new Date(d.created_at), 'HH:mm:ss') : '',
    recv: d.net_bytes_recv_mb ?? 0,
    sent: d.net_bytes_sent_mb ?? 0,
  }))

  const recv = current.net_bytes_recv_mb ?? 0
  const sent = current.net_bytes_sent_mb ?? 0

  return (
    <div className="glass-card p-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300">Network I/O</h3>
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1 text-blue-400">
            <ArrowDown className="w-3 h-3" />
            <span className="tabular-nums font-bold">{recv.toFixed(1)}</span>
            <span className="text-gray-500">MB</span>
          </div>
          <div className="flex items-center gap-1 text-violet-400">
            <ArrowUp className="w-3 h-3" />
            <span className="tabular-nums font-bold">{sent.toFixed(1)}</span>
            <span className="text-gray-500">MB</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id="grad-recv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0}   />
            </linearGradient>
            <linearGradient id="grad-sent" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#8b5cf6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0}   />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" hide />
          <YAxis tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotoneX" dataKey="recv" name="Inbound"  stroke="#3b82f6"
            strokeWidth={1.5} fill="url(#grad-recv)" dot={false} isAnimationActive={false} />
          <Area type="monotoneX" dataKey="sent" name="Outbound" stroke="#8b5cf6"
            strokeWidth={1.5} fill="url(#grad-sent)" dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 justify-center">
        {[{ color: '#3b82f6', label: 'Inbound' }, { color: '#8b5cf6', label: 'Outbound' }].map(l => (
          <div key={l.label} className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="w-2.5 h-0.5 rounded-full" style={{ background: l.color }} />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  )
}
