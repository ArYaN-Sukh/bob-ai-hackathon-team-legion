import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Wand2, FileText, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { getCapa, generateCapa, updateCapa, getDeviation } from '../api/client'
import DeviationBadge from '../components/DeviationBadge'

export default function CapaReport() {
  const { capaId } = useParams<{ capaId: string }>()!
  const qc = useQueryClient()

  const { data: capa, isLoading } = useQuery({
    queryKey: ['capa', capaId],
    queryFn: () => getCapa(Number(capaId)),
    enabled: !!capaId,
  })

  const { data: deviation } = useQuery({
    queryKey: ['deviation', capa?.deviation_id],
    queryFn: () => getDeviation(capa!.deviation_id),
    enabled: !!capa?.deviation_id,
  })

  const genMutation = useMutation({
    mutationFn: () => generateCapa(capa!.deviation_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['capa', capaId] }),
  })

  if (isLoading || !capa) {
    return <div className="p-8 text-center text-text-tertiary">Loading CAPA...</div>
  }

  return (
    <div className="space-y-section">
      <Link to="/capa" className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to CAPA
      </Link>

      {/* Header */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-clinical-navy p-2 rounded-lg">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-text-primary">CAPA Report #{capa.id}</h1>
              <div className="text-sm text-text-secondary mt-1">
                Corrective and Preventive Action
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium px-3 py-1.5 rounded-lg border ${
              capa.status === 'Closed' 
                ? 'bg-risk-low-light text-risk-low border-risk-low'
                : capa.status === 'Open'
                ? 'bg-severity-minor-light text-severity-minor border-severity-minor'
                : 'bg-surface-alt text-text-secondary border-border'
            }`}>
              {capa.status === 'Closed' && <CheckCircle className="w-3 h-3" />}
              {capa.status === 'Open' && <Clock className="w-3 h-3" />}
              {capa.status}
            </span>
          </div>
        </div>
      </div>

      {/* Deviation context */}
      {deviation && (
        <div className="bg-surface rounded-lg border border-border shadow-card p-6">
          <h2 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Related Deviation
          </h2>
          <div className="flex items-center gap-2 mb-3">
            <span className="font-mono text-text-secondary">#{deviation.id}</span>
            <DeviationBadge value={deviation.severity} type="severity" />
            <DeviationBadge value={deviation.status} type="status" />
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-text-secondary">Patient:</span> <Link to={`/patients/${deviation.patient_id}`} className="font-mono text-clinical-navy hover:underline">{deviation.patient_id}</Link></div>
            <div><span className="text-text-secondary">Site:</span> <Link to={`/sites/${deviation.site_id}`} className="text-clinical-navy hover:underline">{deviation.site_id}</Link></div>
            <div><span className="text-text-secondary">Rule:</span> <span className="font-mono text-text-secondary">{deviation.rule_id}</span></div>
            <div><span className="text-text-secondary">Type:</span> <span className="text-text-primary">{deviation.deviation_type}</span></div>
          </div>
          <div className="mt-3 text-sm text-text-secondary bg-surface-alt rounded p-3 border border-border">
            {deviation.description}
          </div>
        </div>
      )}

      {/* CAPA sections */}
      <div className="bg-surface rounded-lg border border-border shadow-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-text-primary">CAPA Content</h2>
          <button
            onClick={() => genMutation.mutate()}
            disabled={genMutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 bg-clinical-navy text-white rounded-lg text-sm hover:bg-clinical-navy-light disabled:opacity-50 transition-colors"
          >
            <Wand2 className="w-3.5 h-3.5" />
            {genMutation.isPending ? 'Generating…' : 'Generate with AI'}
          </button>
        </div>

        {capa.watsonx_narrative ? (
          <div>
            <div className={`text-xs px-2 py-1 rounded mb-3 inline-block ${
              capa.source === 'watsonx'
                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                : 'bg-surface-alt text-text-secondary border border-border'
            }`}>
              {capa.source === 'watsonx' ? '✨ AI-generated by watsonx.ai' : '📋 Fallback template'}
            </div>
            <div className="text-sm bg-surface-alt border border-border rounded p-4 whitespace-pre-wrap text-text-primary leading-relaxed">
              {capa.watsonx_narrative}
            </div>
          </div>
        ) : (
          <div className="text-sm text-text-tertiary text-center py-8">
            No AI narrative yet — click "Generate with AI" to create one.
          </div>
        )}

        {/* Manual fields */}
        <div className="mt-4 space-y-4 text-sm">
          {capa.root_cause && (
            <div>
              <div className="font-medium text-text-primary mb-2">Root Cause Analysis</div>
              <div className="bg-surface-alt rounded p-3 border border-border text-text-secondary">{capa.root_cause}</div>
            </div>
          )}
          {capa.corrective_action && (
            <div>
              <div className="font-medium text-text-primary mb-2">Corrective Action</div>
              <div className="bg-surface-alt rounded p-3 border border-border text-text-secondary">{capa.corrective_action}</div>
            </div>
          )}
          {capa.preventive_action && (
            <div>
              <div className="font-medium text-text-primary mb-2">Preventive Action</div>
              <div className="bg-surface-alt rounded p-3 border border-border text-text-secondary">{capa.preventive_action}</div>
            </div>
          )}
        </div>

        <div className="mt-4 flex gap-6 text-xs text-text-tertiary">
          <div>Due: {capa.due_date ? new Date(capa.due_date).toLocaleDateString() : 'Not set'}</div>
          <div>Closed: {capa.closed_date ? new Date(capa.closed_date).toLocaleDateString() : 'Open'}</div>
        </div>
      </div>
    </div>
  )
}
