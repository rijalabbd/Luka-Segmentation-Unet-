export type PatientTrendBadge =
  | 'belum_ada'
  | 'baseline'
  | 'menurun'
  | 'stabil'
  | 'meningkat'
  | 'tidak_dapat_dihitung'

export interface PatientSummary {
  id: string
  nama: string | null
  umur: number | null
  jk: string | null
  lokasi: string | null
  n: number
  terakhir: string
  status: PatientTrendBadge
  trend_status: string
  is_demo: boolean
}

export interface PatientCreatePayload {
  id: string
  nama?: string | null
  umur?: number | null
  jk?: string | null
  lokasi?: string | null
  consent: boolean
}

export interface HealthResponse {
  status: string
  mode: string
  label: string
  short_label: string
}

export interface VisitRecord {
  id: number
  patient_id: string
  visit_date: string
  status: 'draft' | 'final'
  visit_index: number | null
  image_path: string | null
  mask_path: string | null
  overlay_path: string | null
  distance_confirmed: boolean
  n_wound_px: number
  area_pct: number
  delta_area: number | null
  pac: number | null
  trend_status: string | null
  clinician_notes: string | null
  patient_narrative: string | null
  narrative_source: 'llm' | 'template_fallback' | null
  created_at: string
  confirmed_at: string | null
}
