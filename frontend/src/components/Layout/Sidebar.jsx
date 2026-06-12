import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, LineChart, BellRing, Cpu,
  Zap, Server, Activity,
} from 'lucide-react'
import { useMetrics } from '../../context/MetricsContext'

const NAV = [
  { to: '/',           icon: LayoutDashboard, label: 'Dashboard'  },
  { to: '/analytics',  icon: LineChart,       label: 'Analytics'  },
  { to: '/alerts',     icon: BellRing,        label: 'Alerts'     },
  { to: '/processes',  icon: Cpu,             label: 'Processes'  },
]

const WS_STATUS = {
  connected:    { dot: 'bg-green-500 animate-pulse-slow', label: 'Live',         ring: 'ring-green-500/30' },
  connecting:   { dot: 'bg-yellow-500 animate-pulse',     label: 'Connecting…',  ring: 'ring-yellow-500/30' },
  disconnected: { dot: 'bg-red-500',                      label: 'Disconnected', ring: 'ring-red-500/30' },
  error:        { dot: 'bg-red-500',                      label: 'Error',        ring: 'ring-red-500/30' },
}

function MiniBar({ value, color }) {
  return (
    <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ${color}`}
        style={{ width: `${Math.min(100, value)}%` }}
      />
    </div>
  )
}

export default function Sidebar() {
  const { wsStatus, alertCount, anomalyCount, current } = useMetrics()
  const status = WS_STATUS[wsStatus] ?? WS_STATUS.connecting

  return (
    <aside className="flex flex-col w-60 min-h-screen bg-dark-200 border-r border-white/[0.06] py-5">

      {/* ── Logo ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 mb-7">
        <div className={`p-2 rounded-xl bg-brand-primary/20 ring-1 ${status.ring} transition-all`}>
          <Zap className="w-4 h-4 text-brand-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-bold text-white leading-none tracking-tight">CloudPulse</p>
          <p className="text-[10px] text-gray-500 mt-0.5 font-medium uppercase tracking-wider">AI Monitor</p>
        </div>
      </div>

      {/* ── Connection pill ───────────────────────────────────────────── */}
      <div className="px-5 mb-5">
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] ring-1 ${status.ring}`}>
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${status.dot}`} />
          <span className="text-xs font-medium text-gray-300">{status.label}</span>
          {wsStatus === 'connected' && (
            <Activity className="w-3 h-3 text-green-500 ml-auto" />
          )}
        </div>
      </div>

      {/* ── Section label ─────────────────────────────────────────────── */}
      <p className="section-title">Navigation</p>

      {/* ── Nav links ─────────────────────────────────────────────────── */}
      <nav className="flex flex-col gap-0.5 px-3 flex-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span>{label}</span>
            {label === 'Alerts' && alertCount > 0 && (
              <span className="ml-auto badge badge-danger text-[10px] py-0 animate-bounce-in">
                {alertCount > 99 ? '99+' : alertCount}
              </span>
            )}
            {label === 'Dashboard' && anomalyCount > 0 && (
              <span className="ml-auto badge badge-warning text-[10px] py-0">
                {anomalyCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* ── Live mini-stats ───────────────────────────────────────────── */}
      {wsStatus === 'connected' && (
        <div className="mx-3 mt-4 mb-2 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-2.5">
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
            <Server className="w-3 h-3" /> Live
          </p>
          <div className="space-y-2">
            {[
              { label: 'CPU', value: current.cpu_percent, color: 'bg-indigo-500' },
              { label: 'RAM', value: current.ram_percent, color: 'bg-green-500'  },
              { label: 'Disk', value: current.disk_percent, color: 'bg-amber-500' },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <div className="flex justify-between mb-1">
                  <span className="text-[10px] text-gray-500">{label}</span>
                  <span className="text-[10px] font-mono text-gray-300">{(value || 0).toFixed(1)}%</span>
                </div>
                <MiniBar value={value || 0} color={
                  value >= 85 ? 'bg-red-500' : value >= 65 ? 'bg-amber-500' : color
                } />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <div className="px-5 pt-3 border-t border-white/[0.05]">
        <p className="text-[10px] text-gray-600 font-medium">LEARNING PROJECT</p>
        <p className="text-[10px] text-gray-700">CloudPulse v1.0.0</p>
      </div>
    </aside>
  )
}
