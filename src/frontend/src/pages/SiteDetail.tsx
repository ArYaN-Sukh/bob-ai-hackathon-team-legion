import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, AlertTriangle, User, TrendingUp, FileText } from 'lucide-react'
import { getSite, getSiteRiskHistory, getDeviations, getPatients, getSiteReport } from '../api/client'
import DeviationBadge from '../components/DeviationBadge'
import EmptyState from '../components/EmptyState'

const TIER_BADGE: Record<string, string> = {
  High: 'bg-risk-high-light text-risk-high border border-risk-high',
  Medium: 'bg-risk-medium-light text-risk-medium border border-risk-medium',
  Low: 'bg-risk-low-light text-risk-low border border-risk-low',
}

export default function SiteDetail() {
  const { siteId } = useParams<{ siteId: string }>()!

  const { data: site } = useQuery({
    queryKey: ['site', siteId],
    queryFn: () => getSite(siteId!),
    enabled: !!siteId,
  })

  const { data: deviations = [] } = useQuery({
    queryKey: ['deviations', siteId],
    queryFn: () => getDeviations({ site_id: siteId, status: 'Open', limit: 50 }),
    enabled: !!siteId,
  })

  const { data: patients = [] } = useQuery({
    queryKey: ['patients', siteId],
    queryFn: () => getPatients(siteId),
    enabled: !!siteId,
  })

  const { data: riskHistory = [] } = useQuery({
    queryKey: ['risk-history', siteId],
    queryFn: () => getSiteRiskHistory(siteId!),
    enabled: !!siteId,
  })

  const { data: report, isLoading: reportLoading, refetch: fetchReport } = useQuery({
    queryKey: ['report', siteId],
    queryFn: () => getSiteReport(siteId!),
    enabled: false,
  })

  if (!site) return <div className="p-8 text-center text-text-tertiary">Loading site...</div>

  const majorCount = deviations.filter(d => d.severity === 'Major').length
  const minorCount = deviations.filter(d => d.severity === 'Minor').length
  const adminCount = deviations.filter(d => d.severity === 'Administrative').length

  const latestRisk = riskHistory[0]

  return (
    <div className="space-y-section">
      {/* Back link */}
      <Link to="/" className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </Link>

      {/* Site Header */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-6">
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-semibold text-text-primary">{site.name}</h1>
              {site.latest_risk_tier && (
                <span className={`text-sm font-medium px-3 py-1 rounded-lg border ${TIER_BADGE[site.latest_risk_tier] ?? 'bg-surface-alt'}`}>
                  {site.latest_risk_tier} RISK
                </span>
              )}
            </div>
            <div className="text-sm text-text-secondary mt-1">
              {site.city}, {site.country} — PI: {site.principal_investigator}
            </div>
            <div className="mt-4 flex gap-6 text-sm">
              <div className="text-text-secondary">
                Enrolled: <span className="font-semibold text-text-primary">{site.enrolled_count} / {site.target_enrollment}</span>
              </div>
              <div className="text-text-secondary">
                Status: <span className="font-semibold text-text-primary">{site.status}</span>
              </div>
            </div>
          </div>
          <div className="bg-surface-alt rounded-lg p-4 min-w-[200px] border border-border">
            <div className="text-xs text-text-tertiary uppercase tracking-wide mb-1">Risk Score</div>
            <div className="text-3xl font-semibold text-text-primary">
              {site.latest_risk_score?.toFixed(1) ?? '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Risk Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-surface rounded-lg border border-border shadow-card p-card">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-severity-major" />
            <span className="text-sm font-medium text-text-secondary">Major Deviations</span>
          </div>
          <div className="text-2xl font-semibold text-severity-major">{site.open_major_count}</div>
        </div>
        <div className="bg-surface rounded-lg border border-border shadow-card p-card">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-severity-minor" />
            <span className="text-sm font-medium text-text-secondary">Minor Deviations</span>
          </div>
          <div className="text-2xl font-semibold text-severity-minor">{site.open_minor_count}</div>
        </div>
        <div className="bg-surface rounded-lg border border-border shadow-card p-card">
          <div className="flex items-center gap-2 mb-2">
            <User className="w-4 h-4 text-severity-admin" />
            <span className="text-sm font-medium text-text-secondary">Patients</span>
          </div>
          <div className="text-2xl font-semibold text-text-primary">{patients.length}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-section">
        {/* Patients */}
        <div className="bg-surface rounded-lg border border-border shadow-card">
          <div className="px-card py-3 border-b border-border-light">
            <h2 className="font-semibold text-text-primary flex items-center gap-2">
              <User className="w-4 h-4" />
              Patients ({patients.length})
            </h2>
          </div>
          <div className="divide-y divide-border-light max-h-[400px] overflow-y-auto">
            {patients.slice(0, 10).map(p => (
              <Link
                key={p.id}
                to={`/patients/${p.id}`}
                className="flex items-center justify-between px-card py-3 hover:bg-surface-alt transition-colors"
              >
                <div>
                  <div className="font-mono font-medium text-clinical-navy">{p.id}</div>
                  <div className="text-xs text-text-secondary">Age {p.age} · {p.sex}</div>
                </div>
                {p.open_deviation_count > 0 && (
                  <span className="text-xs bg-severity-major-light text-severity-major rounded px-2 py-0.5 font-medium">
                    {p.open_deviation_count} open
                  </span>
                )}
              </Link>
            ))}
            {patients.length === 0 && <EmptyState message="No patients" />}
          </div>
        </div>

        {/* Open Deviations */}
        <div className="lg:col-span-2 bg-surface rounded-lg border border-border shadow-card">
          <div className="px-card py-3 border-b border-border-light flex items-center justify-between">
            <h2 className="font-semibold text-text-primary flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Open Deviations ({deviations.length})
            </h2>
            <div className="flex gap-3 text-xs">
              <span className="text-severity-major font-medium">{majorCount} Major</span>
              <span className="text-severity-minor font-medium">{minorCount} Minor</span>
              <span className="text-severity-admin font-medium">{adminCount} Admin</span>
            </div>
          </div>
          <div className="overflow-y-auto max-h-[400px]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-alt text-left text-xs text-text-secondary uppercase tracking-wide">
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Rule</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {deviations.map(d => (
                  <tr key={d.id} className="hover:bg-surface-alt transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/patients/${d.patient_id}`} className="font-mono text-clinical-navy hover:underline">
                        {d.patient_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-text-secondary">{d.rule_id}</td>
                    <td className="px-4 py-3">
                      <DeviationBadge value={d.severity} type="severity" size="sm" />
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{d.detected_date}</td>
                  </tr>
                ))}
                {deviations.length === 0 && (
                  <tr><td colSpan={4}><EmptyState message="No open deviations" /></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Report */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-text-primary flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Monitoring Report
          </h2>
          <button
            onClick={() => fetchReport()}
            disabled={reportLoading}
            className="px-4 py-2 text-sm bg-clinical-navy text-white rounded-lg hover:bg-clinical-navy-light disabled:opacity-50 transition-colors"
          >
            {reportLoading ? 'Generating…' : 'Generate Report'}
          </button>
        </div>
        {report && (
          <pre className="text-xs bg-surface-alt border border-border rounded p-4 overflow-auto max-h-96 whitespace-pre-wrap text-text-secondary">
            {report.report_markdown}
          </pre>
        )}
      </div>
    </div>
  )
}
