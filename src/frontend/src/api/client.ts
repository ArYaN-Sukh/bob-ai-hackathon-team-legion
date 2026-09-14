import axios from 'axios'
import type {
  AnalysisRunResponse,
  Capa,
  CapaGenerateResponse,
  Deviation,
  Patient,
  PatientSummary,
  PatientTimeline,
  Site,
  SiteReportResponse,
  SiteRiskScore,
  Trial,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({ baseURL: BASE })

// ── Trials ────────────────────────────────────────────────────────────────────
export const getTrials = () => api.get<Trial[]>('/trials').then(r => r.data)
export const getTrial = (id: string) => api.get<Trial>(`/trials/${id}`).then(r => r.data)
export const getTrialProtocol = (id: string) => api.get<object>(`/trials/${id}/protocol`).then(r => r.data)

// ── Sites ─────────────────────────────────────────────────────────────────────
export const getSites = () => api.get<Site[]>('/sites').then(r => r.data)
export const getSite = (id: string) => api.get<Site>(`/sites/${id}`).then(r => r.data)
export const getSiteRiskHistory = (id: string) =>
  api.get<SiteRiskScore[]>(`/sites/${id}/risk-history`).then(r => r.data)

// ── Patients ──────────────────────────────────────────────────────────────────
export const getPatients = (siteId?: string) => {
  const params = siteId ? { site_id: siteId } : {}
  return api.get<PatientSummary[]>('/patients', { params }).then(r => r.data)
}

export const getPatientSummaries = () => {
  return api.get<PatientSummary[]>('/patients').then(r => r.data)
}

export const getPatient = (id: string) =>
  api.get<Patient>(`/patients/${id}`).then(r => r.data)
export const getPatientTimeline = (id: string) =>
  api.get<PatientTimeline>(`/patients/${id}/timeline`).then(r => r.data)
export const analysePatient = (id: string) =>
  api.post<{ patient_id: string; deviations_created: number; total_open_deviations: number }>(
    `/patients/${id}/analyse`
  ).then(r => r.data)

// ── Deviations ────────────────────────────────────────────────────────────────
export const getDeviations = (params?: {
  site_id?: string
  patient_id?: string
  severity?: string
  status?: string
  limit?: number
}) => api.get<Deviation[]>('/deviations', { params }).then(r => r.data)

export const getDeviation = (id: number) =>
  api.get<Deviation>(`/deviations/${id}`).then(r => r.data)

export const patchDeviation = (id: number, data: { status?: string }) =>
  api.patch<Deviation>(`/deviations/${id}`, data).then(r => r.data)

// ── CAPA ──────────────────────────────────────────────────────────────────────
export const getCapas = (params?: { site_id?: string; status?: string }) =>
  api.get<Capa[]>('/capa', { params }).then(r => r.data)

export const getCapa = (id: number) =>
  api.get<Capa>(`/capa/${id}`).then(r => r.data)

export const updateCapa = (id: number, data: Partial<Capa>) =>
  api.put<Capa>(`/capa/${id}`, data).then(r => r.data)

export const generateCapa = (deviationId: number) =>
  api.post<CapaGenerateResponse>('/capa/generate', { deviation_id: deviationId }).then(r => r.data)

// ── Analysis ──────────────────────────────────────────────────────────────────
export const runAnalysis = () =>
  api.post<AnalysisRunResponse>('/analysis/run').then(r => r.data)

// ── Reports ───────────────────────────────────────────────────────────────────
export const getSiteReport = (siteId: string) =>
  api.get<SiteReportResponse>(`/reports/site/${siteId}`).then(r => r.data)

// ── MCP (Bob) ─────────────────────────────────────────────────────────────────
export const mcpCall = async (toolName: string, args: Record<string, unknown>) => {
  const resp = await axios.post('/mcp', {
    jsonrpc: '2.0',
    id: Date.now(),
    method: 'tools/call',
    params: { name: toolName, arguments: args },
  })
  return resp.data
}

// ── Ask Bob (AI response generation) ─────────────────────────────────────────
export interface BobResponse {
  response: string
  source: 'nvidia' | 'fallback' | 'system'
  tool_used: string
}

export const askBob = async (question: string) => {
  const resp = await api.post<BobResponse>('/bob/ask', { question })
  return resp.data
}
