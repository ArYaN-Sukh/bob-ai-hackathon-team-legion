/**
 * TypeScript types mirroring the FastAPI response schemas.
 */

export interface Trial {
  id: string
  name: string
  protocol_version: string
  sponsor: string
  phase: string
  indication: string
  start_date: string
  end_date: string | null
  target_enrollment: number
  primary_endpoint: string | null
  created_at: string
}

export interface Site {
  id: string
  trial_id: string
  name: string
  city: string | null
  country: string
  principal_investigator: string
  status: string
  enrolled_count: number
  target_enrollment: number
  activation_date: string | null
  created_at: string
  // Risk enrichment fields
  latest_risk_score: number | null
  latest_risk_tier: 'High' | 'Medium' | 'Low' | null
  open_major_count: number
  open_minor_count: number
  open_admin_count: number
}

export interface SiteRiskScore {
  id: number
  site_id: string
  score_date: string
  major_open_count: number
  minor_open_count: number
  admin_open_count: number
  avg_capa_age_days: number
  data_query_rate_pct: number
  enrollment_deviation_pct: number
  total_score: number
  risk_tier: 'High' | 'Medium' | 'Low'
  created_at: string
}

export interface Patient {
  id: string
  site_id: string
  trial_id: string
  age: number
  sex: string
  ecog_score: number | null
  diagnosis_confirmed: boolean
  prior_egfr_alk_treatment_days: number | null
  active_infection: boolean
  pregnant_or_breastfeeding: boolean
  consent_signed_before_procedure: boolean
  enrollment_date: string
  status: string
  created_at: string
}

export interface PatientSummary {
  id: string
  site_id: string
  age: number
  sex: string
  status: string
  enrollment_date: string
  open_deviation_count: number
}

export interface Visit {
  id: number
  patient_id: string
  site_id: string
  visit_number: number
  visit_name: string
  visit_type: string
  scheduled_date: string
  actual_date: string | null
  window_deviation_days: number | null
  completed_assessments: string[] | null
  notes: string | null
  created_at: string
}

export interface LabResult {
  id: number
  patient_id: string
  visit_id: number
  test_name: string
  display_name: string
  value: number
  unit: string
  reference_low: number | null
  reference_high: number | null
  collection_date: string
  is_out_of_range: boolean
  created_at: string
}

export interface AdverseEvent {
  id: number
  patient_id: string
  site_id: string
  description: string
  onset_date: string
  sae_flag: boolean
  expected_flag: boolean
  reported_date: string | null
  reporting_delay_hours: number | null
  severity_grade: number | null
  outcome: string | null
  created_at: string
}

export type DeviationSeverity = 'Major' | 'Minor' | 'Administrative'
export type DeviationStatus = 'Open' | 'Closed' | 'Pending Review'

export interface Deviation {
  id: number
  patient_id: string
  visit_id: number | null
  site_id: string
  rule_id: string
  deviation_type: string
  description: string
  severity: DeviationSeverity
  status: DeviationStatus
  detected_date: string
  evidence: string | null
  created_at: string
  updated_at: string
}

export interface Capa {
  id: number
  deviation_id: number
  site_id: string
  root_cause: string | null
  corrective_action: string | null
  preventive_action: string | null
  watsonx_narrative: string | null
  source: 'watsonx' | 'fallback' | null
  due_date: string | null
  closed_date: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface TimelineVisit {
  visit_id: number
  visit_number: number
  visit_name: string
  scheduled_date: string
  actual_date: string | null
  window_deviation_days: number | null
  deviations: Deviation[]
  lab_results: LabResult[]
}

export interface PatientTimeline {
  patient: Patient
  visits: TimelineVisit[]
  all_deviations: Deviation[]
  adverse_events: AdverseEvent[]
}

export interface AnalysisRunResponse {
  deviations_created: number
  total_open_deviations: number
  sites_scored: number
  site_risk_summary: Array<{
    site_id: string
    total_score: number
    risk_tier: string
    major_open_count: number
    minor_open_count: number
    admin_open_count: number
  }>
}

export interface CapaGenerateResponse {
  capa_id: number
  deviation_id: number
  narrative: string
  source: 'watsonx' | 'fallback'
}

export interface SiteReportResponse {
  site_id: string
  report_markdown: string
  generated_at: string
}
