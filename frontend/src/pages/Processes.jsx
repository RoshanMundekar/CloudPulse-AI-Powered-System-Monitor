/**
 * Processes page — live sortable process table with search highlighting.
 *
 * Enhancements:
 * - Highlighted search matches
 * - CPU bar colored by severity (green → amber → red)
 * - RAM bar track
 * - Sort arrow on active column
 * - "No processes yet" vs "No search results" empty states
 * - Animated entry on data arrive
 */
import { useState, useMemo } from 'react'
import { Search, ArrowUp, ArrowDown } from 'lucide-react'
import { useMetrics } from '../context/MetricsContext'
import Header from '../components/Layout/Header'

function Highlight({ text, query }) {
  if (!query) return <>{text}</>
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-brand-primary/30 text-white rounded px-0.5">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  )
}

function CpuBar({ value }) {
  const color = value >= 50 ? 'bg-red-500' : value >= 25 ? 'bg-amber-500' : 'bg-indigo-500'
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
      <span className="font-mono text-xs text-gray-300 tabular-nums w-10 text-right">
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

function RamBar({ value }) {
  return (
    <div className="flex items-center gap-2 min-w-[72px]">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-green-500 transition-all duration-700"
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
      <span className="font-mono text-xs text-gray-300 tabular-nums w-10 text-right">
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

const COLS = [
  { key: 'pid',            label: 'PID',    sortable: false },
  { key: 'name',           label: 'Name',   sortable: false },
  { key: 'cpu_percent',    label: 'CPU',    sortable: true  },
  { key: 'memory_percent', label: 'RAM',    sortable: true  },
  { key: 'status',         label: 'Status', sortable: false },
]

export default function Processes() {
  const { current, initialized } = useMetrics()
  const [search,   setSearch]   = useState('')
  const [sortKey,  setSortKey]  = useState('cpu_percent')
  const [sortDir,  setSortDir]  = useState('desc')

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const processes = useMemo(() => {
    return [...(current.top_processes || [])]
      .filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) =>
        sortDir === 'desc'
          ? b[sortKey] - a[sortKey]
          : a[sortKey] - b[sortKey]
      )
  }, [current.top_processes, search, sortKey, sortDir])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header title="Processes" />
      <main className="flex-1 overflow-y-auto p-5 space-y-4">

        {/* Search */}
        <div className="flex items-center gap-3">
          <div className="relative max-w-xs flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
            <input
              type="text"
              placeholder="Search process name…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="input pl-9"
            />
          </div>
          <p className="text-xs text-gray-500 tabular-nums">
            {processes.length} / {current.top_processes?.length ?? 0} processes
          </p>
        </div>

        {/* Table */}
        <div className="glass-card overflow-hidden animate-fade-in">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                  {COLS.map(col => (
                    <th
                      key={col.key}
                      onClick={() => col.sortable && toggleSort(col.key)}
                      className={`px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wider
                                  text-gray-500 select-none whitespace-nowrap
                                  ${col.sortable ? 'cursor-pointer hover:text-gray-300 transition-colors' : ''}`}
                    >
                      <div className="flex items-center gap-1">
                        {col.label}
                        {col.sortable && sortKey === col.key && (
                          sortDir === 'desc'
                            ? <ArrowDown className="w-3 h-3 text-brand-primary" />
                            : <ArrowUp   className="w-3 h-3 text-brand-primary" />
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!initialized || !current.top_processes?.length ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-gray-500 text-sm">
                      Waiting for agent data…
                    </td>
                  </tr>
                ) : processes.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-gray-500 text-sm">
                      No processes match <span className="text-gray-400">"{search}"</span>
                    </td>
                  </tr>
                ) : (
                  processes.map((proc, i) => (
                    <tr
                      key={proc.pid}
                      className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
                    >
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-500 tabular-nums">
                        {proc.pid}
                      </td>
                      <td className="px-4 py-2.5 font-medium text-white max-w-[180px]">
                        <span className="truncate block">
                          <Highlight text={proc.name} query={search} />
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <CpuBar value={proc.cpu_percent} />
                      </td>
                      <td className="px-4 py-2.5">
                        <RamBar value={proc.memory_percent} />
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`badge text-[10px]
                          ${proc.status === 'running'  ? 'badge-success' :
                            proc.status === 'sleeping' ? 'badge-info'    : 'badge-ghost'}`}>
                          {proc.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  )
}
