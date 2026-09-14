import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileText, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { getCapas } from '../api/client'

export default function Capa() {
  const { data: capas, isLoading, error } = useQuery({
    queryKey: ['capas'],
    queryFn: () => getCapas(),
  })

  if (isLoading) return <div className="p-8 text-center text-text-tertiary">Loading CAPA...</div>
  if (error) return <div className="p-8 text-center text-severity-major">Failed to load CAPA.</div>

  return (
    <div className="space-y-section">
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">CAPA</h1>
        <p className="text-sm text-text-secondary mt-1">
          Corrective and preventive actions generated from protocol deviations.
        </p>
      </div>

      <div className="bg-surface rounded-lg border border-border shadow-card overflow-hidden">
        <div className="px-card py-3 border-b border-border-light">
          <h2 className="font-semibold text-text-primary">All CAPA</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-alt text-left text-xs text-text-secondary uppercase tracking-wide">
                <th className="px-4 py-3">CAPA ID</th>
                <th className="px-4 py-3">Deviation ID</th>
                <th className="px-4 py-3">Site</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Due Date</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {capas && capas.length > 0 ? capas.map(capa => (
                <tr key={capa.id} className="hover:bg-surface-alt transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      to={`/capa/${capa.id}`}
                      className="font-mono font-medium text-clinical-navy hover:underline"
                    >
                      CAPA-{capa.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{capa.deviation_id}</td>
                  <td className="px-4 py-3 text-text-secondary">{capa.site_id}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded ${
                      capa.status === 'Closed' 
                        ? 'bg-risk-low-light text-risk-low'
                        : capa.status === 'Open'
                        ? 'bg-severity-minor-light text-severity-minor'
                        : 'bg-surface-alt text-text-secondary'
                    }`}>
                      {capa.status === 'Closed' && <CheckCircle className="w-3 h-3" />}
                      {capa.status === 'Open' && <Clock className="w-3 h-3" />}
                      {capa.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${
                      capa.source === 'watsonx' 
                        ? 'text-clinical-navy'
                        : 'text-text-tertiary'
                    }`}>
                      {capa.source === 'watsonx' ? 'AI' : 'Fallback'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {capa.due_date ? new Date(capa.due_date).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/capa/${capa.id}`}
                      className="text-sm text-clinical-navy hover:underline font-medium"
                    >
                      View Report
                    </Link>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-text-tertiary">
                    No CAPA records found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
