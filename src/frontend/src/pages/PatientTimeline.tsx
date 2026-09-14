import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle, AlertTriangle, Activity } from 'lucide-react'
import { getPatientTimeline, generateCapa } from '../api/client'
import DeviationBadge from '../components/DeviationBadge'
import type { Deviation } from '../types'

function VisitDot({ windowDays }: { windowDays: number | null }) {
  if (!windowDays) return <span className="w-3 h-3 rounded-full bg-risk-low inline-block" />
  const abs = Math.abs(windowDays)
  if (abs <= 2) return <span className="w-3 h-3 rounded-full bg-risk-low inline-block" />
  if (abs <= 5) return <span className="w-3 h-3 rounded-full bg-severity-minor inline-block" />
  return <span className="w-3 h-3 rounded-full bg-severity-major inline-block" />
}

export default function PatientTimeline() {
  const { patientId } = useParams<{ patientId: string }>()!
  const qc = useQueryClient()

  const { data: timeline, isLoading } = useQuery({
    queryKey: ['timeline', patientId],
    queryFn: () => getPatientTimeline(patientId!),
    enabled: !!patientId,
  })

  const capaMutation = useMutation({
    mutationFn: (devId: number) => generateCapa(devId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['capas'] }),
  })

  if (isLoading || !timeline) {
    return <div className="p-8 text-center text-text-tertiary">Loading patient timeline...</div>
  }

  const { patient, visits, all_deviations, adverse_events } = timeline
  const openDevs = all_deviations.filter(d => d.status === 'Open')

  return (
    <div className="space-y-section">
      <Link to={`/sites/${patient.site_id}`} className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to Site {patient.site_id}
      </Link>

      {/* Patient header */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-text-primary">{patient.id}</h1>
            <div className="text-sm text-text-secondary mt-1">
              Age {patient.age} · {patient.sex} · ECOG {patient.ecog_score ?? '?'} · {patient.status}
            </div>
            <div className="text-sm text-text-secondary mt-1">
              Site: {patient.site_id} · Enrolled: {patient.enrollment_date}
            </div>
          </div>
          <div className="bg-surface-alt rounded-lg p-4 min-w-[120px] border border-border text-center">
            <div className="text-xs text-text-tertiary uppercase tracking-wide mb-1">Open Deviations</div>
            <div className="text-3xl font-semibold text-severity-major">{openDevs.length}</div>
          </div>
        </div>
      </div>

      {/* Visit timeline */}
      <div className="bg-surface rounded-lg border border-border shadow-card">
        <div className="px-card py-3 border-b border-border-light">
          <h2 className="font-semibold text-text-primary flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Visit Timeline
          </h2>
        </div>
        <div className="p-6 space-y-4">
          {visits.map(visit => (
            <div key={visit.visit_id} className="flex gap-4">
              <div className="flex flex-col items-center">
                <VisitDot windowDays={visit.window_deviation_days} />
                <div className="w-0.5 bg-border flex-1 mt-1" />
              </div>
              <div className="flex-1 pb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm text-text-primary">{visit.visit_name}</span>
                  {visit.window_deviation_days !== null && Math.abs(visit.window_deviation_days) > 3 && (
                    <span className="text-xs bg-severity-minor-light text-severity-minor rounded px-2 py-0.5 border border-severity-minor">
                      {visit.window_deviation_days > 0 ? '+' : ''}{visit.window_deviation_days}d
                    </span>
                  )}
                </div>
                <div className="text-xs text-text-secondary mb-2">
                  Scheduled: {visit.scheduled_date}
                  {visit.actual_date && ` · Actual: ${visit.actual_date}`}
                </div>

                {/* Deviations at this visit */}
                {visit.deviations.map((d: Deviation) => (
                  <div key={d.id} className="flex items-start gap-2 text-xs mt-1.5 bg-surface-alt rounded p-2 border border-border">
                    <DeviationBadge value={d.severity} type="severity" size="sm" />
                    <div className="flex-1">
                      <span className="font-mono text-text-secondary">{d.rule_id}</span>
                      <span className="mx-1 text-text-tertiary">·</span>
                      <span className="text-text-primary">{d.description}</span>
                    </div>
                    <button
                      onClick={() => capaMutation.mutate(d.id)}
                      disabled={capaMutation.isPending}
                      className="text-clinical-navy hover:underline shrink-0 disabled:opacity-50 font-medium"
                    >
                      {capaMutation.isPending && capaMutation.variables === d.id ? 'Generating…' : 'CAPA'}
                    </button>
                  </div>
                ))}

                {/* Out-of-range labs */}
                {visit.lab_results.filter(lr => lr.is_out_of_range).map(lr => (
                  <div key={lr.id} className="text-xs mt-1 text-severity-minor bg-severity-minor-light rounded px-3 py-1.5 border border-severity-minor">
                    ⚠ {lr.display_name}: {lr.value} {lr.unit}
                    {lr.reference_high && ` (ref: ${lr.reference_low ?? '?'}–${lr.reference_high})`}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Non-visit deviations (eligibility) */}
      {all_deviations.filter(d => !d.visit_id).length > 0 && (
        <div className="bg-surface rounded-lg border border-border shadow-card p-6">
          <h2 className="font-semibold text-text-primary mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Eligibility / Non-Visit Deviations
          </h2>
          <div className="space-y-2">
            {all_deviations.filter(d => !d.visit_id).map(d => (
              <div key={d.id} className="flex items-start gap-2 text-xs bg-severity-major-light rounded p-3 border border-severity-major">
                <DeviationBadge value={d.severity} type="severity" size="sm" />
                <div className="flex-1">
                  <span className="font-mono text-text-secondary">{d.rule_id}</span>
                  <span className="mx-1 text-text-tertiary">·</span>
                  <span className="text-text-primary">{d.description}</span>
                </div>
                <DeviationBadge value={d.status} type="status" size="sm" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CAPA result */}
      {capaMutation.isSuccess && (
        <div className="bg-risk-low-light border border-risk-low rounded-lg p-6">
          <div className="flex items-center gap-2 mb-2 text-sm font-medium text-risk-low">
            <CheckCircle className="w-4 h-4" />
            CAPA Generated ({capaMutation.data.source})
          </div>
          <pre className="text-xs whitespace-pre-wrap text-text-secondary">
            {capaMutation.data.narrative}
          </pre>
        </div>
      )}

      {/* Adverse events */}
      {adverse_events.length > 0 && (
        <div className="bg-surface rounded-lg border border-border shadow-card p-6">
          <h2 className="font-semibold text-text-primary mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Adverse Events ({adverse_events.length})
          </h2>
          <div className="space-y-1.5">
            {adverse_events.map(ae => (
              <div key={ae.id} className={`text-xs rounded p-3 border ${ae.sae_flag ? 'bg-severity-major-light border-severity-major' : 'bg-surface-alt border-border'}`}>
                <span className={ae.sae_flag ? 'font-bold text-severity-major' : 'text-text-primary'}>
                  {ae.sae_flag ? '[SAE] ' : ''}
                </span>
                {ae.description}
                {ae.reporting_delay_hours && ae.reporting_delay_hours > 24 && (
                  <span className="ml-2 text-severity-major">⚠ Delayed {ae.reporting_delay_hours.toFixed(0)}h</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
