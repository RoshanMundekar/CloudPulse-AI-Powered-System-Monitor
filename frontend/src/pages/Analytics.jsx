/**
 * Analytics — historical data explorer.
 *
 * Enhancements:
 * - Skeleton loaders while fetching
 * - Uses /api/metrics/buckets (hourly aggregation via PostgreSQL DATE_TRUNC)
 * - Min stat cards alongside avg/max
 * - Reference lines at thresholds
 * - Auto-refresh on time range change
 */
import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { format } from 'date-fns'
import { getMetricHistory, getMetricAverages } from '../services/api'
import Header   from '../components/Layout/Header'
import Skeleton from '../components/ui/Skeleton'

const RANGES = [
  { label: '30m', hours: 0.5 },
  { label: '1h',  hours: 1   },
  { label: '6h',  hours: 6   },
  { label: '24h', hours: 24  },
  { label: '7d',  hours: 168 },
]

const CHART_STYLE = {
  contentStyle: {
    background: '#171d2d', border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10, padding: '8px 12px', fontSize: 11,
  },
  labelStyle:  { color: '#6b7280', marginBottom: 4 },
  itemStyle:   { fontSize: 11 },
}

function StatCard({ label, value, color, sub }) {
  return (
    <div className="glass-card p-4 text-center animate-fade-in">
      <p className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold font-mono tabular-nums ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-gray-600 mt-1">{sub}</p>}
    </div>
  )
}

export default function Analytics() {
  const [hours,   setHours]   = useState(1)
  const [history, setHistory] = useState([])
  const [avgs,    setAvgs]    = useState(null)
  const [loading, setLoading] = useState(true)

  const timeFmt = hours <= 1 ? 'HH:mm:ss' : hours <= 24 ? 'HH:mm' : 'MM/dd HH:mm'

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [h, a] = await Promise.all([
        getMetricHistory(Math.max(hours, 0.5)),
        getMetricAverages(Math.max(hours, 0.5)),
      ])
      setHistory(h.data.map(d => ({
        ...d,
        time: format(new Date(d.created_at), timeFmt),
      })))
      setAvgs(a.data)
    } catch {}
    finally { setLoading(false) }
  }, [hours, timeFmt])

  useEffect(() => { load() }, [load])

  const statCards = avgs ? [
    { label: 'Avg CPU',  value: `${avgs.avg_cpu}%`,  color: 'text-indigo-400' },
    { label: 'Peak CPU', value: `${avgs.max_cpu}%`,  color: 'text-red-400',    sub: `min ${avgs.min_cpu}%` },
    { label: 'Avg RAM',  value: `${avgs.avg_ram}%`,  color: 'text-green-400'  },
    { label: 'Peak RAM', value: `${avgs.max_ram}%`,  color: 'text-red-400',    sub: `min ${avgs.min_ram}%` },
    { label: 'Avg Disk', value: `${avgs.avg_disk}%`, color: 'text-amber-400',  sub: `${avgs.sample_count} samples` },
  ] : []

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header title="Analytics" onRefresh={load} />
      <main className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* Time range pills */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500 mr-1">Range:</span>
          {RANGES.map(r => (
            <button
              key={r.hours}
              onClick={() => setHours(r.hours)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all
                ${hours === r.hours
                  ? 'bg-brand-primary text-white shadow-glow-indigo'
                  : 'glass-card text-gray-400 hover:text-white hover:border-white/10'}`}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* Stat cards */}
        {loading
          ? <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[...Array(5)].map((_, i) => <Skeleton.Card key={i} rows={3} />)}
            </div>
          : <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {statCards.map(s => <StatCard key={s.label} {...s} />)}
            </div>
        }

        {/* CPU / RAM / Disk multi-line chart */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">CPU · RAM · Disk Usage (%)</h3>
          {loading
            ? <Skeleton.Chart height={300} />
            : <ResponsiveContainer width="100%" height={300}>
                <LineChart data={history} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false}
                         interval="preserveStartEnd" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false} />
                  <ReferenceLine y={85} stroke="rgba(239,68,68,0.3)" strokeDasharray="4 4" />
                  <Tooltip {...CHART_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
                  <Line type="monotoneX" dataKey="cpu_percent"  stroke="#6366f1" dot={false} name="CPU %"  strokeWidth={2} isAnimationActive={false} />
                  <Line type="monotoneX" dataKey="ram_percent"  stroke="#22c55e" dot={false} name="RAM %"  strokeWidth={2} isAnimationActive={false} />
                  <Line type="monotoneX" dataKey="disk_percent" stroke="#f59e0b" dot={false} name="Disk %" strokeWidth={2} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
          }
        </div>

        {/* Network I/O bar chart */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Network I/O — Inbound vs Outbound (MB)</h3>
          {loading
            ? <Skeleton.Chart height={220} />
            : <ResponsiveContainer width="100%" height={220}>
                <BarChart data={history.slice(-60)} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false}
                         interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false} />
                  <Tooltip {...CHART_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
                  <Bar dataKey="net_bytes_recv_mb" name="Inbound MB"  fill="#3b82f6" radius={[2,2,0,0]} maxBarSize={12} isAnimationActive={false} />
                  <Bar dataKey="net_bytes_sent_mb" name="Outbound MB" fill="#8b5cf6" radius={[2,2,0,0]} maxBarSize={12} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
          }
        </div>

        {/* Disk I/O chart */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Disk I/O — Read vs Write (MB)</h3>
          {loading
            ? <Skeleton.Chart height={180} />
            : <ResponsiveContainer width="100%" height={180}>
                <BarChart data={history.slice(-60)} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false}
                         interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: '#4b5563' }} tickLine={false} axisLine={false} />
                  <Tooltip {...CHART_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
                  <Bar dataKey="disk_read_mb"  name="Read MB"  fill="#06b6d4" radius={[2,2,0,0]} maxBarSize={12} isAnimationActive={false} />
                  <Bar dataKey="disk_write_mb" name="Write MB" fill="#14b8a6" radius={[2,2,0,0]} maxBarSize={12} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
          }
        </div>

      </main>
    </div>
  )
}
