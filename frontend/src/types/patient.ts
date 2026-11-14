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

export interface VisitPreview {
  is_baseline: boolean
  pac_basis: 'relative' | 'calibrated' | null
  delta_area: number | null
  pac: number | null
  pac_rel: number | null
  pac_cm2: number | null
  trend_status: string | null
  warnings: string[]
}

export interface CalibrationPayload {
  x1: number
  y1: number
  x2: number
  y2: number
  length_cm: number
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
  confirm_zero_area: boolean
  n_wound_px: number
  area_pct: number
  delta_area: number | null
  pac: number | null
  trend_status: string | null
  measure_mode: 'relative' | 'calibrated'
  img_width_px: number | null
  img_height_px: number | null
  calib_x1: number | null
  calib_y1: number | null
  calib_x2: number | null
  calib_y2: number | null
  calib_length_cm: number | null
  scale_cm_per_px: number | null
  area_cm2: number | null
  pac_rel: number | null
  pac_cm2: number | null
  pac_basis: 'relative' | 'calibrated' | null
  warnings: string[] | null
  preview: VisitPreview | null
  clinician_notes: string | null
  patient_narrative: string | null
  narrative_source: 'llm' | 'template_fallback' | null
  created_at: string
  confirmed_at: string | null
}
