/**
 * Dashboard — main real-time monitoring view.
 *
 * Layout:
 *   ① Anomaly banner (conditional, pulsing red)
 *   ② System status bar (hostname · platform · uptime · ws)
 *   ③ 4 metric cards with sparklines
 *   ④ CPU + RAM large area charts (side-by-side)
 *   ⑤ Disk chart + Network I/O card (side-by-side)
 *   ⑥ Alerts panel + Anomaly feed (side-by-side)
 */
import { Cpu, MemoryStick, HardDrive } from 'lucide-react'
import { useMetrics } from '../context/MetricsContext'
import MetricCard    from '../components/Dashboard/MetricCard'
import LiveChart     from '../components/Dashboard/LiveChart'
import NetworkCard   from '../components/Dashboard/NetworkCard'
import SystemStatus  from '../components/Dashboard/SystemStatus'
import AlertsPanel   from '../components/Alerts/AlertsPanel'
import AnomalyFeed   from '../components/Anomalies/AnomalyFeed'
import Header        from '../components/Layout/Header'
import Skeleton      from '../components/ui/Skeleton'

export default function Dashboard() {
  const { current, history, anomalyCount, initialized } = useMetrics()

  const cards = [
    {
      title:      'CPU Usage',
      value:      current.cpu_percent,
      icon:       Cpu,
      subtitle:   current.cpu_count ? `${current.cpu_count} logical cores` : '—',
      dataKey:    'cpu_percent',
      sparkColor: '#6366f1',
    },
    {
      title:   'RAM Usage',
      value:   current.ram_percent,
      icon:    MemoryStick,
      subtitle: current.ram_used_gb != null
        ? `${current.ram_used_gb.toFixed(1)} / ${current.ram_total_gb?.toFixed(0) ?? '?'} GB`
        : '—',
      dataKey:    'ram_percent',
      sparkColor: '#22c55e',
    },
    {
      title:   'Disk Usage',
      value:   current.disk_percent,
      icon:    HardDrive,
      subtitle: current.disk_used_gb != null
        ? `${current.disk_used_gb.toFixed(0)} / ${current.disk_total_gb?.toFixed(0) ?? '?'} GB`
        : '—',
      dataKey:    'disk_percent',
      sparkColor: '#f59e0b',
    },
    {
      title:      'Disk I/O',
      value:      ((current.disk_read_mb ?? 0) + (current.disk_write_mb ?? 0)).toFixed(1),
      unit:       'MB',
      icon:       HardDrive,
      subtitle:   `R: ${(current.disk_read_mb ?? 0).toFixed(1)} · W: ${(current.disk_write_mb ?? 0).toFixed(1)} MB`,
      dataKey:    'disk_read_mb',
      sparkColor: '#06b6d4',
    },
  ]

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header title="Dashboard" />

      <main className="flex-1 overflow-y-auto p-5 space-y-4">

        {/* ① Anomaly banner */}
        {anomalyCount > 0 && (
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl
                          bg-red-500/8 border border-red-500/25 animate-fade-in">
            <span className="live-dot bg-red-500" />
            <p className="text-sm text-red-300 font-medium">
              <span className="font-bold text-red-400">{anomalyCount}</span>
              {' '}anomal{anomalyCount === 1 ? 'y' : 'ies'} detected by AI in the last hour
            </p>
          </div>
        )}

        {/* ② System status bar */}
        <SystemStatus />

        {/* ③ Metric cards */}
        {!initialized ? (
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => <Skeleton.Card key={i} rows={4} />)}
          </div>
        ) : (
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
            {cards.map(card => (
              <MetricCard key={card.title} {...card} history={history} />
            ))}
          </div>
        )}

        {/* ④ CPU + RAM charts */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <LiveChart
            title="CPU Usage"
            data={history}
            dataKey="cpu_percent"
            color="#6366f1"
            threshold={85}
          />
          <LiveChart
            title="RAM Usage"
            data={history}
            dataKey="ram_percent"
            color="#22c55e"
            threshold={85}
          />
        </div>

        {/* ⑤ Disk + Network */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <LiveChart
            title="Disk Usage"
            data={history}
            dataKey="disk_percent"
            color="#f59e0b"
            threshold={90}
            height={150}
          />
          <NetworkCard history={history} current={current} />
        </div>

        {/* ⑥ Alerts + Anomaly feed */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <AlertsPanel limit={6} />
          <AnomalyFeed limit={6} />
        </div>

      </main>
    </div>
  )
}
