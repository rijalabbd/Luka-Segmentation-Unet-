import type {
  CalibrationPayload,
  HealthResponse,
  PatientCreatePayload,
  PatientSummary,
  VisitRecord,
} from '@/types/patient'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) return body.detail[0].msg
  } catch {
    return fallback
  }
  return fallback
}

export async function checkServerHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new ApiError(res.status, 'Server lokal tidak merespons dengan benar.')
  }
  return (await res.json()) as HealthResponse
}

export async function fetchPatients(): Promise<PatientSummary[]> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/patients`, {
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(
      0,
      'Tidak dapat terhubung ke server backend lokal (/api/v1/patients). Pastikan layanan backend dan basis data sedang berjalan.',
    )
  }

  if (!res.ok) {
    throw new ApiError(res.status, `Gagal memuat daftar pasien (HTTP ${res.status}).`)
  }
  return (await res.json()) as PatientSummary[]
}

export async function createPatient(payload: PatientCreatePayload): Promise<PatientSummary> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/patients`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new ApiError(
      0,
      'Tidak dapat menghubungi server backend lokal. Pendaftaran pasien tidak dapat disimpan saat server offline.',
    )
  }

  if (!res.ok) {
    throw new ApiError(res.status, await readErrorDetail(res, 'Gagal menyimpan data pasien.'))
  }

  return (await res.json()) as PatientSummary
}

export function resolveStorageUrl(relPath: string | null | undefined): string {
  if (!relPath) return ''
  const clean = relPath.replace(/^\/+/, '')
  return `${API_BASE}/storage/${clean}`
}

export async function fetchPatient(patientId: string): Promise<PatientSummary> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/patients/${encodeURIComponent(patientId)}`, {
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(
      0,
      'Tidak dapat terhubung ke server backend lokal untuk memuat data pasien.',
    )
  }
  if (!res.ok) {
    const fallback =
      res.status === 404
        ? `Data pasien ${patientId} tidak ditemukan.`
        : `Tidak dapat menghubungi server backend lokal (HTTP ${res.status}). Pastikan layanan backend sedang berjalan.`
    throw new ApiError(res.status, await readErrorDetail(res, fallback))
  }
  return (await res.json()) as PatientSummary
}

export async function fetchPatientVisits(
  patientId: string,
  status: 'final' | 'draft' | 'all' = 'final',
): Promise<VisitRecord[]> {
  let res: Response
  const query = status !== 'final' ? `?status=${encodeURIComponent(status)}` : ''
  try {
    res = await fetch(`${API_BASE}/patients/${encodeURIComponent(patientId)}/visits${query}`, {
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(
      0,
      'Tidak dapat terhubung ke server backend lokal untuk memuat riwayat kunjungan.',
    )
  }
  if (!res.ok) {
    throw new ApiError(res.status, `Gagal memuat riwayat kunjungan (HTTP ${res.status}).`)
  }
  return (await res.json()) as VisitRecord[]
}

export async function deleteVisit(visitId: number): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/visits/${encodeURIComponent(String(visitId))}`, {
      method: 'DELETE',
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server backend lokal untuk menghapus kunjungan.')
  }
  if (!res.ok) {
    const fallback =
      res.status === 404
        ? `Data kunjungan #${visitId} tidak ditemukan atau sudah dihapus.`
        : res.status === 409
          ? 'Kunjungan tidak dapat dihapus karena melanggar aturan LIFO (hanya kunjungan terakhir yang boleh dihapus).'
          : `Gagal menghapus kunjungan (HTTP ${res.status}).`
    throw new ApiError(res.status, await readErrorDetail(res, fallback))
  }
}

export async function deletePatient(
  patientId: string,
): Promise<{ deleted_patient_id: string; deleted_visits: number }> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/patients/${encodeURIComponent(patientId)}`, {
      method: 'DELETE',
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server backend lokal saat menghapus data pasien.')
  }
  if (!res.ok) {
    const fallback =
      res.status === 404
        ? `Data pasien ${patientId} tidak ditemukan atau sudah dihapus.`
        : res.status === 409
          ? 'Data pasien tidak dapat dihapus karena masih ada operasi aktif.'
          : `Gagal menghapus data pasien (HTTP ${res.status}).`
    throw new ApiError(res.status, await readErrorDetail(res, fallback))
  }
  return (await res.json()) as { deleted_patient_id: string; deleted_visits: number }
}

export async function createDraftVisit(
  patientId: string,
  visitDate: string,
  file: File,
  distanceConfirmed = true,
): Promise<VisitRecord> {
  const formData = new FormData()
  formData.append('visit_date', visitDate)
  formData.append('distance_confirmed', distanceConfirmed ? 'true' : 'false')
  formData.append('file', file, file.name)

  let res: Response
  try {
    res = await fetch(`${API_BASE}/patients/${encodeURIComponent(patientId)}/visits`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: formData,
    })
  } catch {
    throw new ApiError(
      0,
      'Tidak dapat terhubung ke server backend lokal saat menjalankan deteksi luka.',
    )
  }

  if (!res.ok) {
    throw new ApiError(
      res.status,
      await readErrorDetail(res, `Gagal memproses foto luka (HTTP ${res.status}).`),
    )
  }

  return (await res.json()) as VisitRecord
}

export async function fetchDemoSamplePhoto(patientId: string): Promise<File> {
  let res: Response
  try {
    res = await fetch(
      `${API_BASE}/patients/${encodeURIComponent(patientId)}/sample-photo`,
      {
        headers: { Accept: 'image/jpeg' },
      },
    )
  } catch {
    throw new ApiError(
      0,
      'Tidak dapat terhubung ke server backend lokal untuk mengambil foto sampel demo.',
    )
  }

  if (!res.ok) {
    throw new ApiError(
      res.status,
      await readErrorDetail(res, `Gagal memuat foto sampel demo (HTTP ${res.status}).`),
    )
  }

  const blob = await res.blob()
  const filename = res.headers.get('X-Sample-Filename')?.trim() || 'foto_sampel_demo.jpg'
  return new File([blob], filename, { type: blob.type || 'image/jpeg' })
}

export async function fetchVisit(visitId: number): Promise<VisitRecord> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/visits/${encodeURIComponent(String(visitId))}`, {
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server backend lokal untuk memuat data kunjungan.')
  }
  if (!res.ok) {
    const fallback =
      res.status === 404
        ? `Data kunjungan #${visitId} tidak ditemukan.`
        : `Gagal memuat data kunjungan (HTTP ${res.status}).`
    throw new ApiError(res.status, await readErrorDetail(res, fallback))
  }
  return (await res.json()) as VisitRecord
}

export async function putVisitCalibration(
  visitId: number,
  payload: CalibrationPayload,
): Promise<VisitRecord> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/visits/${encodeURIComponent(String(visitId))}/calibration`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server backend lokal untuk menyimpan kalibrasi.')
  }
  if (!res.ok) {
    throw new ApiError(
      res.status,
      await readErrorDetail(res, `Gagal menyimpan kalibrasi (HTTP ${res.status}).`),
    )
  }
  return (await res.json()) as VisitRecord
}

export async function deleteVisitCalibration(visitId: number): Promise<VisitRecord> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/visits/${encodeURIComponent(String(visitId))}/calibration`, {
      method: 'DELETE',
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server backend lokal untuk menghapus kalibrasi.')
  }
  if (!res.ok) {
    throw new ApiError(
      res.status,
      await readErrorDetail(res, `Gagal menghapus kalibrasi (HTTP ${res.status}).`),
    )
  }
  return (await res.json()) as VisitRecord
}

export async function confirmVisit(
  visitId: number,
  confirmZeroArea = false,
): Promise<VisitRecord> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/visits/${encodeURIComponent(String(visitId))}/confirm`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ confirm_zero_area: confirmZeroArea }),
    })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server backend lokal saat mengonfirmasi kunjungan.')
  }
  if (!res.ok) {
    throw new ApiError(
      res.status,
      await readErrorDetail(res, `Gagal mengonfirmasi kunjungan (HTTP ${res.status}).`),
    )
  }
  return (await res.json()) as VisitRecord
}
