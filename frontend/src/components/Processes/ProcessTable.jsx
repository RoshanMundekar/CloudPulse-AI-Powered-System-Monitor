/**
 * ProcessTable — sortable table of top processes by CPU usage.
 */
import { useState } from 'react'
import { useMetrics } from '../../context/MetricsContext'
import { ArrowUpDown } from 'lucide-react'

export default function ProcessTable() {
  const { current } = useMetrics()
  const [sortKey, setSortKey] = useState('cpu_percent')

  const processes = [...(current.top_processes || [])]
    .sort((a, b) => b[sortKey] - a[sortKey])

  const cols = [
    { key: 'pid',            label: 'PID'    },
    { key: 'name',           label: 'Name'   },
    { key: 'cpu_percent',    label: 'CPU %'  },
    { key: 'memory_percent', label: 'RAM %'  },
    { key: 'status',         label: 'Status' },
  ]

  if (!processes.length) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-sm text-gray-500">No process data yet. Waiting for agent...</p>
      </div>
    )
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-white/5">
        <h3 className="text-sm font-semibold text-gray-300">Top Processes</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5">
              {cols.map(col => (
                <th
                  key={col.key}
                  onClick={() => setSortKey(col.key)}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-400 cursor-pointer hover:text-white transition-colors select-none"
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    {sortKey === col.key && <ArrowUpDown className="w-3 h-3" />}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {processes.map((proc, i) => (
              <tr key={proc.pid} className={`border-b border-white/5 hover:bg-white/2 transition-colors ${i % 2 === 0 ? '' : 'bg-white/[0.01]'}`}>
                <td className="px-4 py-2.5 font-mono text-xs text-gray-400">{proc.pid}</td>
                <td className="px-4 py-2.5 font-medium text-white truncate max-w-[160px]">{proc.name}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full"
                        style={{ width: `${Math.min(100, proc.cpu_percent)}%` }}
                      />
                    </div>
                    <span className="font-mono text-xs text-gray-300">{proc.cpu_percent.toFixed(1)}%</span>
                  </div>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-gray-300">{proc.memory_percent.toFixed(1)}%</td>
                <td className="px-4 py-2.5">
                  <span className={`badge ${proc.status === 'running' ? 'badge-success' : 'badge-info'}`}>
                    {proc.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
