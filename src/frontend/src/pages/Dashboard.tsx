import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { RefreshCw, AlertTriangle, Shield, Activity, Users, TrendingUp } from 'lucide-react'
import { getSites, runAnalysis } from '../api/client'
import type { Site } from '../types'

const TIER_BADGE: Record<string, string> = {
  High: 'bg-risk-high-light text-risk-high border border-risk-high',
  Medium: 'bg-risk-medium-light text-risk-medium border border-risk-medium',
  Low: 'bg-risk-low-light text-risk-low border border-risk-low',
}

function KpiCard({ title, value, icon: Icon, colour, trend }: {
  title: string; value: string | number; icon: React.ElementType; colour: string; trend?: string
}) {
  return (
    <div className="bg-surface rounded-lg border border-border shadow-card p-card">
      <div className="flex items-start justify-between">
        <div className={`p-2.5 rounded-lg ${colour}`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <span className="text-xs text-text-tertiary flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            {trend}
          </span>
        )}
      </div>
      <div className="mt-3">
        <div className="text-2xl font-semibold text-text-primary">{value}</div>
        <div className="text-xs text-text-secondary mt-0.5">{title}</div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const qc = useQueryClient()
  const { data: sites, isLoading, error } = useQuery({
    queryKey: ['sites'],
    queryFn: getSites,
  })

  const analysisMutation = useMutation({
    mutationFn: runAnalysis,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sites'] })
      qc.invalidateQueries({ queryKey: ['deviations'] })
    },
  })

  if (isLoading) return <div className="p-8 text-center text-text-tertiary">Loading sites...</div>
  if (error) return <div className="p-8 text-center text-severity-major">Failed to load sites.</div>

  const sorted = [...(sites || [])].sort((a, b) =>
    (b.latest_risk_score ?? 0) - (a.latest_risk_score ?? 0)
  )

  const highRisk = sorted.filter(s => s.latest_risk_tier === 'High').length
  const totalMajor = sorted.reduce((acc, s) => acc + s.open_major_count, 0)
  const totalMinor = sorted.reduce((acc, s) => acc + s.open_minor_count, 0)
  const totalEnrolled = sorted.reduce((acc, s) => acc + s.enrolled_count, 0)

  return (
    <div className="space-y-section">
      {/* Trial Header */}
      <div className="bg-clinical-navy rounded-lg p-6 shadow-elevation">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">Site Risk & Protocol Deviation Overview</h1>
            <p className="text-sm text-white/70 mt-1">
              Phase II Study of Compound XR-447 — Advanced NSCLC
            </p>
          </div>
          <button
            onClick={() => analysisMutation.mutate()}
            disabled={analysisMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-white text-clinical-navy rounded-lg text-sm font-medium hover:bg-white/90 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${analysisMutation.isPending ? 'animate-spin' : ''}`} />
            {analysisMutation.isPending ? 'Running…' : 'Run Analysis'}
          </button>
        </div>
        <div className="mt-4 flex items-center gap-4 text-xs text-white/60">
          <span>Last analysis: {new Date().toLocaleDateString()}</span>
          <span>•</span>
          <span>Data status: Live</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard 
          title="High-Risk Sites" 
          value={highRisk} 
          icon={AlertTriangle} 
          colour="bg-risk-high-light text-risk-high" 
        />
        <KpiCard 
          title="Open Major Deviations" 
          value={totalMajor} 
          icon={Shield} 
          colour="bg-severity-major-light text-severity-major" 
        />
        <KpiCard 
          title="Open Minor Deviations" 
          value={totalMinor} 
          icon={Activity} 
          colour="bg-severity-minor-light text-severity-minor" 
        />
        <KpiCard 
          title="Patients Enrolled" 
          value={totalEnrolled} 
          icon={Users} 
          colour="bg-severity-admin-light text-severity-admin" 
        />
      </div>

      {/* Sites Table */}
      <div className="bg-surface rounded-lg border border-border shadow-card overflow-hidden">
        <div className="px-card py-3 border-b border-border-light flex items-center justify-between">
          <h2 className="font-semibold text-text-primary">All Sites</h2>
          <span className="text-xs text-text-tertiary">{sorted.length} sites</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-alt text-left text-xs text-text-secondary uppercase tracking-wide">
                <th className="px-4 py-3">Site</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Enrollment</th>
                <th className="px-4 py-3">Risk Tier</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Major</th>
                <th className="px-4 py-3">Minor</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {sorted.map(site => (
                <tr key={site.id} className="hover:bg-surface-alt transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      to={`/sites/${site.id}`}
                      className="font-mono font-medium text-clinical-navy hover:underline"
                    >
                      {site.id}
                    </Link>
                    <div className="text-xs text-text-secondary truncate max-w-[150px]">{site.name}</div>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {site.city}, {site.country}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-text-primary">{site.enrolled_count} / {site.target_enrollment}</span>
                      <div className="w-16 bg-border rounded-full h-1.5">
                        <div
                          className="bg-clinical-navy h-1.5 rounded-full"
                          style={{ width: `${Math.min((site.enrolled_count / site.target_enrollment) * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {site.latest_risk_tier ? (
                      <span className={`text-xs font-medium px-2 py-0.5 rounded border ${TIER_BADGE[site.latest_risk_tier] ?? 'bg-surface-alt'}`}>
                        {site.latest_risk_tier}
                      </span>
                    ) : (
                      <span className="text-text-tertiary text-xs">N/A</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-sm text-text-primary">
                    {site.latest_risk_score?.toFixed(1) ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-severity-major font-medium">{site.open_major_count}</td>
                  <td className="px-4 py-3 text-severity-minor font-medium">{site.open_minor_count}</td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/sites/${site.id}`}
                      className="text-sm text-clinical-navy hover:underline font-medium"
                    >
                      View Details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
