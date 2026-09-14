import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { getDeviations } from '../api/client'
import DeviationBadge from '../components/DeviationBadge'
import EmptyState from '../components/EmptyState'

const SEVERITY_OPTIONS = ['All', 'Major', 'Minor', 'Administrative']
const STATUS_OPTIONS = ['All', 'Open', 'Closed', 'Pending Review']

export default function DeviationLog() {
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState('All')
  const [status, setStatus] = useState('Open')

  const { data: deviations = [], isLoading } = useQuery({
    queryKey: ['deviations', severity, status],
    queryFn: () =>
      getDeviations({
        severity: severity !== 'All' ? severity : undefined,
        status: status !== 'All' ? status : undefined,
        limit: 200,
      }),
  })

  const filtered = deviations.filter(d => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      d.rule_id.toLowerCase().includes(q) ||
      d.patient_id.toLowerCase().includes(q) ||
      d.description.toLowerCase().includes(q)
    )
  })

  const hasFilters = search || severity !== 'All' || status !== 'All'

  const clearFilters = () => {
    setSearch('')
    setSeverity('All')
    setStatus('Open')
  }

  return (
    <div className="space-y-section">
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">Deviation Log</h1>
        <p className="text-sm text-text-secondary mt-1">
          Investigate protocol deviations detected across the trial.
        </p>
      </div>

      {/* Filters */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search rule ID, patient, description..."
                className="w-full pl-10 pr-4 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clinical-navy focus:border-transparent bg-surface"
              />
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <label className="text-xs text-text-secondary">Severity:</label>
            <select
              value={severity}
              onChange={e => setSeverity(e.target.value)}
              className="px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clinical-navy bg-surface"
            >
              {SEVERITY_OPTIONS.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-text-secondary">Status:</label>
            <select
              value={status}
              onChange={e => setStatus(e.target.value)}
              className="px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clinical-navy bg-surface"
            >
              {STATUS_OPTIONS.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
            >
              <X className="w-3 h-3" />
              Clear ({(search ? 1 : 0) + (severity !== 'All' ? 1 : 0) + (status !== 'All' ? 1 : 0)})
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface rounded-lg border border-border shadow-card overflow-hidden">
        <div className="px-card py-3 border-b border-border-light flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">Deviations</h2>
          <span className="text-xs text-text-tertiary">{filtered.length} result{filtered.length !== 1 ? 's' : ''}</span>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-text-tertiary">Loading deviations...</div>
        ) : filtered.length === 0 ? (
          <EmptyState message="No deviations match the current filters." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-alt text-left text-xs text-text-secondary uppercase tracking-wide">
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Site</th>
                  <th className="px-4 py-3">Rule</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Detected</th>
                  <th className="px-4 py-3">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {filtered.map(d => (
                  <tr key={d.id} className="hover:bg-surface-alt transition-colors">
                    <td className="px-4 py-3 font-mono text-text-secondary">#{d.id}</td>
                    <td className="px-4 py-3">
                      <Link to={`/patients/${d.patient_id}`} className="font-mono text-clinical-navy hover:underline">
                        {d.patient_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/sites/${d.site_id}`} className="text-clinical-navy hover:underline">
                        {d.site_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-text-secondary">{d.rule_id}</td>
                    <td className="px-4 py-3">
                      <DeviationBadge value={d.severity} type="severity" size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      <DeviationBadge value={d.status} type="status" size="sm" />
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{d.detected_date}</td>
                    <td className="px-4 py-3 text-text-secondary max-w-xs truncate">{d.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
