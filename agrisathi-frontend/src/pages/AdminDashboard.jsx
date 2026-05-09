import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API = '/api'

function StatusBadge({ status }) {
  const map = {
    active: 'bg-green-100 text-green-700 border-green-300',
    paused: 'bg-yellow-100 text-yellow-700 border-yellow-300',
    failed: 'bg-red-100 text-red-700 border-red-300',
  }
  return (
    <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded border ${map[status] || 'bg-gray-100 text-gray-600 border-gray-300'}`}>
      {status}
    </span>
  )
}

function TriggerButton({ name }) {
  const [state, setState] = useState('idle') // idle | running | done | error

  async function trigger() {
    setState('running')
    try {
      const res = await fetch(`${API}/sources/${encodeURIComponent(name)}/trigger`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setState('done')
    } catch {
      setState('error')
    } finally {
      setTimeout(() => setState('idle'), 4000)
    }
  }

  const styles = {
    idle: 'bg-green-600 hover:bg-green-700 text-white',
    running: 'bg-gray-300 text-gray-500 cursor-not-allowed',
    done: 'bg-green-200 text-green-800 cursor-default',
    error: 'bg-red-200 text-red-800 cursor-default',
  }
  const labels = {
    idle: 'Trigger',
    running: 'Running…',
    done: 'Done',
    error: 'Error',
  }

  return (
    <button
      onClick={state === 'idle' ? trigger : undefined}
      disabled={state === 'running'}
      className={`text-xs px-3 py-1.5 rounded font-medium transition-colors ${styles[state]}`}
    >
      {labels[state]}
    </button>
  )
}

function formatDate(val) {
  if (!val) return '—'
  try {
    return new Date(val).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return val
  }
}

export default function AdminDashboard() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  async function fetchSources() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/sources`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSources(data)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  const counts = {
    active: sources.filter((s) => s.status === 'active').length,
    paused: sources.filter((s) => s.status === 'paused').length,
    failed: sources.filter((s) => s.status === 'failed').length,
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-800">AgriSathi Admin — Data Pipeline</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage and trigger data source ingestion jobs
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-sm text-green-600 hover:text-green-700 font-medium border border-green-300 rounded px-3 py-1.5 transition-colors"
          >
            Back to Farmer App
          </Link>
          <button
            onClick={fetchSources}
            className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium rounded px-3 py-1.5 transition-colors"
          >
            Refresh
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-green-600">{counts.active}</div>
            <div className="text-sm text-gray-500">Active sources</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-yellow-500">{counts.paused}</div>
            <div className="text-sm text-gray-500">Paused</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-red-500">{counts.failed}</div>
            <div className="text-sm text-gray-500">Failed</div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
            <span className="font-semibold text-gray-700">Data Sources ({sources.length})</span>
            {lastRefresh && (
              <span className="text-xs text-gray-400">
                Last refreshed: {lastRefresh.toLocaleTimeString('en-IN')}
              </span>
            )}
          </div>

          {loading && (
            <div className="text-center py-12 text-gray-400">Loading sources…</div>
          )}
          {error && (
            <div className="text-center py-12 text-red-500">
              Failed to load sources: {error}
              <br />
              <span className="text-sm text-gray-400">Is the API running at localhost:8000?</span>
            </div>
          )}
          {!loading && !error && sources.length === 0 && (
            <div className="text-center py-12 text-gray-400">No sources found.</div>
          )}

          {!loading && !error && sources.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Name</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Schedule</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Last Fetched</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                    <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sources.map((src) => (
                    <tr key={src.name} className="hover:bg-gray-50 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="font-medium text-gray-800">{src.name}</div>
                        <div className="text-xs text-gray-400 mt-0.5 max-w-xs truncate">{src.url}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="bg-blue-50 text-blue-700 border border-blue-200 text-xs font-semibold px-2 py-0.5 rounded uppercase">
                          {src.source_type}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <code className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-mono">
                          {src.schedule_cron}
                        </code>
                      </td>
                      <td className="px-4 py-3.5 text-gray-600 whitespace-nowrap">
                        {formatDate(src.last_fetched_at)}
                      </td>
                      <td className="px-4 py-3.5">
                        <StatusBadge status={src.status} />
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <TriggerButton name={src.name} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
