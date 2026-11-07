<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  ApiError,
  checkServerHealth,
  confirmVisit,
  deleteVisit,
  fetchPatient,
  fetchPatientVisits,
  fetchVisit,
  resolveStorageUrl,
} from '@/api/patients'
import type { PatientSummary, VisitRecord } from '@/types/patient'

const route = useRoute()
const router = useRouter()

const visitId = computed(() => Number(route.params.visitId))

const serverOnline = ref<boolean | null>(null)
const healthLabel = ref('Server Lokal Terhubung · Data Terisolasi')

const visit = ref<VisitRecord | null>(null)
const patient = ref<PatientSummary | null>(null)
const patientVisits = ref<VisitRecord[]>([])

const isLoading = ref(true)
const loadError = ref('')
const actionError = ref('')
const isConfirming = ref(false)
const isDiscarding = ref(false)

// Tab state for narrative
const activeTab = ref<'patient' | 'clinician'>('patient')

// Toggle overlay
const showOverlay = ref(true)

// Modal states
const showSaveModal = ref(false)
const showDiscardModal = ref(false)
const maskConfirmed = ref(false)
const maskCheckboxError = ref('')

// Tooltip for chart
const hoveredPoint = ref<{
  visitIndex: number
  date: string
  pac: number | null
  areaPct: number
  x: number
  y: number
} | null>(null)

const patientAttrs = computed(() => {
  const p = patient.value
  if (!p) return []
  const items: string[] = []
  if (p.umur !== null && p.umur !== undefined) items.push(`${p.umur} tahun`)
  if (p.jk) items.push(p.jk)
  return items
})

const MONTHS_ID = [
  'Januari',
  'Februari',
  'Maret',
  'April',
  'Mei',
  'Juni',
  'Juli',
  'Agustus',
  'September',
  'Oktober',
  'November',
  'Desember',
]

function formatDateID(isoDate: string | null | undefined): string {
  if (!isoDate) return '-'
  const parts = isoDate.split('-').map(Number)
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return isoDate
  const [y, m, d] = parts
  const monthName = MONTHS_ID[(m ?? 1) - 1] ?? ''
  return `${d} ${monthName} ${y}`
}

const isBaseline = computed(() => {
  const current = visit.value
  if (!current) return false
  if (current.visit_index === 1) return true
  // In draft state, if patient has 0 final visits, this draft is baseline
  const confirmedCount = patientVisits.value.filter((v) => v.status === 'final' && v.id !== current.id).length
  return confirmedCount === 0 && (current.visit_index === null || current.visit_index === 1)
})

const visitDisplayNumber = computed(() => {
  const current = visit.value
  if (!current) return 1
  if (current.visit_index) return current.visit_index
  const confirmedCount = patientVisits.value.filter((v) => v.status === 'final' && v.id !== current.id).length
  return confirmedCount + 1
})

const baselineVisit = computed(() => {
  return patientVisits.value.find((v) => v.status === 'final' && v.visit_index === 1) ?? null
})

const a0Value = computed(() => {
  if (isBaseline.value) return visit.value?.area_pct ?? 0
  return baselineVisit.value?.area_pct ?? null
})

// Trend class helper
const trendClass = computed(() => {
  const status = visit.value?.trend_status ?? ''
  if (status.includes('Menurun')) return 'trend-menurun'
  if (status.includes('Meningkat')) return 'trend-meningkat'
  if (status.includes('Stabil')) return 'trend-stabil'
  return ''
})

// Format helpers
function formatPac(pac: number | null | undefined): string {
  if (pac === null || pac === undefined) return '0.00%'
  const sign = pac > 0 ? '+' : ''
  return `${sign}${pac.toFixed(2)}%`
}

function formatDelta(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return '0.00'
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toFixed(2)}`
}

// Chart computation
interface ChartPoint {
  index: number
  label: string
  date: string
  pac: number | null
  areaPct: number
  x: number
  y: number
  isCurrent: boolean
}

const chartData = computed(() => {
  const allFinal = patientVisits.value
    .filter((v) => v.status === 'final')
    .sort((a, b) => (a.visit_index ?? 0) - (b.visit_index ?? 0))

  const list: { index: number; date: string; pac: number | null; areaPct: number; isCurrent: boolean }[] = []

  // Add final visits
  for (const f of allFinal) {
    list.push({
      index: f.visit_index ?? 1,
      date: formatDateID(f.visit_date),
      pac: f.visit_index === 1 ? 0 : f.pac,
      areaPct: f.area_pct,
      isCurrent: f.id === visit.value?.id,
    })
  }

  // If current visit is draft and not yet in final list, add it as dotted / current point
  if (visit.value && visit.value.status === 'draft') {
    list.push({
      index: visitDisplayNumber.value,
      date: formatDateID(visit.value.visit_date),
      pac: visit.value.pac,
      areaPct: visit.value.area_pct,
      isCurrent: true,
    })
  }

  if (list.length === 0) return { points: [], minPac: -10, maxPac: 10, svgWidth: 320, svgHeight: 180, zeroY: 90 }

  const svgWidth = 300
  const svgHeight = 160
  const padLeft = 46
  const padRight = 24
  const padTop = 20
  const padBottom = 30

  // Calculate Y min and max
  let minP = -5
  let maxP = 25
  for (const item of list) {
    if (item.pac !== null && item.pac !== undefined) {
      if (item.pac < minP) minP = Math.floor(item.pac - 5)
      if (item.pac > maxP) maxP = Math.ceil(item.pac + 5)
    }
  }

  const range = maxP - minP || 1
  const plotH = svgHeight - padTop - padBottom
  const plotW = svgWidth - padLeft - padRight

  const points: ChartPoint[] = list.map((item, idx) => {
    const x = list.length === 1 ? padLeft + plotW / 2 : padLeft + (idx / (list.length - 1)) * plotW
    const pVal = item.pac ?? 0
    const y = padTop + plotH - ((pVal - minP) / range) * plotH
    return {
      ...item,
      label: `T${item.index}`,
      x,
      y,
    }
  })

  const zeroY = padTop + plotH - ((0 - minP) / range) * plotH

  return { points, minPac: minP, maxPac: maxP, svgWidth, svgHeight, zeroY }
})

const chartPolyline = computed(() => {
  return chartData.value.points.map((p) => `${p.x},${p.y}`).join(' ')
})

async function loadData() {
  isLoading.value = true
  loadError.value = ''
  actionError.value = ''

  checkServerHealth()
    .then((h) => {
      serverOnline.value = h.status === 'ok'
      healthLabel.value = h.label
    })
    .catch(() => {
      serverOnline.value = false
      healthLabel.value = 'Server Lokal Tidak Terhubung'
    })

  try {
    const v = await fetchVisit(visitId.value)
    visit.value = v

    const [p, vList] = await Promise.all([
      fetchPatient(v.patient_id),
      fetchPatientVisits(v.patient_id, 'all'),
    ])
    patient.value = p
    patientVisits.value = vList
  } catch (err) {
    if (err instanceof ApiError) {
      loadError.value = err.message
    } else {
      loadError.value = 'Gagal memuat data kunjungan.'
    }
  } finally {
    isLoading.value = false
  }
}

function openSaveModal() {
  actionError.value = ''
  maskConfirmed.value = false
  maskCheckboxError.value = ''
  showSaveModal.value = true
}

function openDiscardModal() {
  actionError.value = ''
  showDiscardModal.value = true
}

async function handleConfirmSave() {
  if (!maskConfirmed.value) {
    maskCheckboxError.value = 'Centang kotak konfirmasi sebelum menyimpan hasil.'
    return
  }

  isConfirming.value = true
  maskCheckboxError.value = ''
  actionError.value = ''

  try {
    const updated = await confirmVisit(visitId.value)
    visit.value = updated
    showSaveModal.value = false
    // Refresh visit list for patient
    if (patient.value) {
      patientVisits.value = await fetchPatientVisits(patient.value.id, 'all')
    }
  } catch (err) {
    if (err instanceof ApiError) {
      actionError.value = err.message
    } else {
      actionError.value = 'Terjadi kesalahan saat mengonfirmasi kunjungan.'
    }
  } finally {
    isConfirming.value = false
  }
}

async function handleDiscardDraft() {
  if (!visit.value) return
  isDiscarding.value = true
  actionError.value = ''

  try {
    const patId = visit.value.patient_id
    await deleteVisit(visit.value.id)
    showDiscardModal.value = false
    await router.push(`/pemeriksaan/${encodeURIComponent(patId)}/unggah`)
  } catch (err) {
    if (err instanceof ApiError) {
      actionError.value = err.message
    } else {
      actionError.value = 'Gagal membuang draf kunjungan.'
    }
    isDiscarding.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="h4-page">
    <a class="skip-link" href="#main-content">Lewati ke konten utama</a>

    <header class="topbar">
      <div class="topbar-in">
        <RouterLink class="brand" to="/" aria-label="Dokumentasi Luka, ke Beranda">
          <span class="brand-mark" aria-hidden="true">+</span>
          <span>
            <span class="brand-name">Dokumentasi Luka</span>
            <span class="brand-sub">Pemantauan Berkala</span>
          </span>
        </RouterLink>
        <div class="topright">
          <div class="sys" role="status">
            <span
              class="dot"
              :class="{ offline: serverOnline === false }"
              aria-hidden="true"
            ></span>
            <span>{{ healthLabel }}</span>
          </div>
          <nav class="topnav" aria-label="Navigasi utama">
            <RouterLink to="/">Beranda</RouterLink>
            <RouterLink to="/pemeriksaan" aria-current="page">Pemeriksaan</RouterLink>
          </nav>
        </div>
      </div>
    </header>

    <main id="main-content" class="main-container">
      <nav class="crumb" aria-label="Breadcrumb">
        <RouterLink
          v-if="visit"
          id="back-to-upload"
          :to="`/pemeriksaan/${encodeURIComponent(visit.patient_id)}/unggah`"
        >
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
            <path d="m15 18-6-6 6-6" />
          </svg>
          Kembali ke Unggah Foto
        </RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ visit?.patient_id || 'Pemeriksaan' }}</span>
      </nav>

      <div v-if="isLoading" class="loading-state" role="status">
        <div class="spinner" aria-hidden="true"></div>
        <p>Memuat data pemeriksaan...</p>
      </div>

      <div v-else-if="loadError" id="load-error-banner" class="error-banner" role="alert">
        <div>
          <strong>Gagal memuat hasil kunjungan</strong>
          <p>{{ loadError }}</p>
        </div>
        <div class="banner-actions">
          <button class="btn btn-primary" type="button" @click="loadData">Coba lagi</button>
          <RouterLink class="btn btn-secondary" to="/pemeriksaan">Pilih Pasien Lain</RouterLink>
        </div>
      </div>

      <template v-else-if="visit">
        <div class="title-row">
          <div>
            <h1>Hasil Pemeriksaan Luka</h1>
            <div class="visit-meta">
              <span id="visit-meta-text">
                Kunjungan ke-{{ visitDisplayNumber }} · {{ formatDateID(visit.visit_date) }}
              </span>
              <span
                id="chip-status"
                class="chip"
                :class="{
                  draft: visit.status === 'draft',
                  final: visit.status === 'final' && !isBaseline,
                  base: visit.status === 'final' && isBaseline,
                }"
              >
                {{
                  visit.status === 'draft'
                    ? 'Draf — Belum Disimpan'
                    : isBaseline
                      ? 'Baseline A₀'
                      : 'Final — Tersimpan'
                }}
              </span>
            </div>
          </div>
        </div>

        <section class="patient" aria-label="Informasi pasien">
          <div class="p-main">
            <span class="rm">{{ patient?.id || visit.patient_id }}</span>
            <span v-if="patient?.nama" class="p-name">{{ patient.nama }}</span>
            <span v-for="(attr, idx) in patientAttrs" :key="idx">{{ attr }}</span>
          </div>
          <div v-if="patient?.lokasi" class="p-loc">
            Lokasi ulkus: <strong>{{ patient.lokasi }}</strong>
          </div>
        </section>

        <!-- Status Banner -->
        <div
          id="banner-box"
          class="banner"
          :class="{
            draft: visit.status === 'draft',
            final: visit.status === 'final' && !isBaseline,
            base: visit.status === 'final' && isBaseline,
          }"
          role="status"
        >
          <svg
            v-if="visit.status === 'draft'"
            class="i banner-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M12 3 2.5 20h19L12 3Z" />
            <path d="M12 10v4M12 17h.01" />
          </svg>
          <svg
            v-else-if="!isBaseline"
            class="i banner-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="m8.5 12.5 2.5 2.5 4.5-5" />
          </svg>
          <svg v-else class="i banner-icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8h.01M11 12h1v4h1" />
          </svg>
          <div>
            <strong v-if="visit.status === 'draft'">Draf — Belum Disimpan</strong>
            <strong v-else-if="!isBaseline">Final — Terkonfirmasi dan Tersimpan</strong>
            <strong v-else>Baseline — Kunjungan Pertama</strong>
            <p v-if="visit.status === 'draft'">
              Hasil pemeriksaan masih berupa draf dan belum disimpan ke riwayat pasien. Periksa
              kembali batas masker segmentasi sebelum melakukan konfirmasi. Jika masker tidak sesuai
              dengan luka, pilih Foto Ulang.
            </p>
            <p v-else-if="!isBaseline">
              Hasil pemeriksaan telah dikonfirmasi dan tersimpan sebagai rekam kunjungan pasien.
            </p>
            <p v-else>
              Kunjungan pertama digunakan sebagai baseline (A₀). Perhitungan PAC baru tersedia mulai
              kunjungan kedua.
            </p>
          </div>
        </div>

        <div v-if="actionError" id="action-error-banner" class="error-banner" role="alert">
          <div>
            <strong>Terjadi Kendala</strong>
            <p>{{ actionError }}</p>
          </div>
        </div>

        <div class="layout">
          <!-- Visual Panel: Foto Asli & Hasil Segmentasi -->
          <section class="panel viz" aria-labelledby="t-viz">
            <div class="viz-head">
              <h2 id="t-viz">Foto Asli dan Hasil Segmentasi</h2>
              <div class="viz-controls">
                <label class="toggle-wrap" for="toggle-mask-overlay">
                  <input id="toggle-mask-overlay" v-model="showOverlay" type="checkbox" />
                  <span>Tampilkan overlay masker hijau</span>
                </label>
                <div class="legend" aria-hidden="true">
                  <span class="sw"></span>
                  <span>Masker luka ({{ visit.n_wound_px }} px)</span>
                </div>
              </div>
            </div>

            <div class="pair">
              <figure class="fig">
                <div class="fig-label">
                  <span>Foto Asli</span>
                  <small>Sebelum segmentasi</small>
                </div>
                <div class="img-box">
                  <img
                    id="img-original"
                    :src="resolveStorageUrl(visit.image_path)"
                    :alt="`Foto asli luka pasien ${visit.patient_id} kunjungan ke-${visitDisplayNumber}`"
                  />
                </div>
              </figure>

              <figure class="fig">
                <div class="fig-label">
                  <span>Hasil Segmentasi</span>
                  <small>{{ showOverlay ? 'Overlay masker hijau' : 'Tanpa masker' }}</small>
                </div>
                <div class="img-box">
                  <img
                    id="img-segmented"
                    :src="
                      showOverlay && visit.overlay_path
                        ? resolveStorageUrl(visit.overlay_path)
                        : resolveStorageUrl(visit.image_path)
                    "
                    :alt="`Hasil segmentasi luka pasien ${visit.patient_id}`"
                  />
                </div>
              </figure>
            </div>
            <p class="viz-note">
              Model inferensi U-Net (ResNet-34) memproses citra 256×256 piksel dengan ambang sigmoid 0,5.
              Masker hijau transparan menunjukkan batas area luka terdeteksi.
            </p>
          </section>

          <!-- Metrics Panel -->
          <div class="metrics">
            <section class="panel metric" aria-labelledby="m1">
              <div id="m1" class="m-label">Estimasi Luas Area Luka (Aₜ)</div>
              <div id="area-val" class="m-value">{{ visit.area_pct.toFixed(2) }}%</div>
              <div class="m-sub">
                Persentase area luka pada citra ({{ visit.n_wound_px.toLocaleString('id-ID') }} / 65.536 piksel)
              </div>
              <p class="m-limit">
                Estimasi relatif terhadap luas citra (% kanvas), tanpa penanda kalibrasi fisik. Bukan ukuran dalam cm².
              </p>
              <p v-if="isBaseline" id="base-note" class="m-note">
                Hasil ini menjadi acuan baseline A₀. Nilai PAC dan grafik tren baru tersedia mulai kunjungan kedua.
              </p>
            </section>

            <!-- PAC Card for follow-up visits -->
            <section
              v-if="!isBaseline"
              id="pac-card"
              class="panel metric"
              aria-labelledby="m2"
            >
              <div id="m2" class="m-label">Perubahan Area Luka (PAC terhadap A₀)</div>
              <template v-if="a0Value === 0">
                <div id="pac-zero-notice" class="pac-zero-box">
                  <strong>Tidak dapat dihitung</strong>
                  <p>PAC tidak dapat dihitung karena luas baseline A₀ = 0% (pembagian nol dicegah).</p>
                </div>
              </template>
              <template v-else>
                <div id="pac-val" class="m-value" :class="trendClass">
                  {{ formatPac(visit.pac) }}
                </div>
                <div class="m-sub">
                  Dihitung terhadap kunjungan baseline A₀ (A₀ = {{ a0Value !== null ? a0Value.toFixed(2) : '-' }}%)
                </div>
                <div v-if="visit.delta_area !== null" class="delta-sub">
                  ΔA: <strong>{{ formatDelta(visit.delta_area) }}</strong> poin persentase
                </div>

                <div
                  v-if="visit.trend_status"
                  id="trend-badge"
                  class="trend"
                  :class="trendClass"
                >
                  <svg
                    v-if="visit.trend_status.includes('Menurun')"
                    class="i"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path d="M7 7l10 10M17 9v8H9" />
                  </svg>
                  <svg
                    v-else-if="visit.trend_status.includes('Meningkat')"
                    class="i"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path d="M7 17 17 7M9 7h8v8" />
                  </svg>
                  <svg v-else class="i" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M5 12h14" />
                  </svg>
                  <span>{{ visit.trend_status }}</span>
                </div>
              </template>
            </section>

            <!-- Grafik Tren PAC -->
            <section
              v-if="!isBaseline && chartData.points.length > 0"
              id="chart-card"
              class="panel chart"
              aria-labelledby="t-chart"
            >
              <h2 id="t-chart">Tren PAC terhadap Baseline A₀</h2>
              <p class="sub">Nilai positif menunjukkan luka mengecil dibandingkan kondisi awal.</p>
              <div id="chart-wrap" class="chart-wrap">
                <svg
                  :viewBox="`0 0 ${chartData.svgWidth} ${chartData.svgHeight}`"
                  aria-label="Grafik garis persentase perubahan area luka terhadap kunjungan awal"
                  role="img"
                >
                  <!-- Grid line at zero baseline -->
                  <g class="grid">
                    <line
                      x1="40"
                      :y1="chartData.zeroY"
                      :x2="chartData.svgWidth - 10"
                      :y2="chartData.zeroY"
                      class="zero-line"
                    />
                    <text x="36" :y="chartData.zeroY + 3" text-anchor="end" class="chart-zero-lbl">
                      0%
                    </text>
                  </g>

                  <!-- Polyline connect points -->
                  <polyline
                    v-if="chartData.points.length > 1"
                    :points="chartPolyline"
                    class="chart-line"
                  />

                  <!-- Points -->
                  <g v-for="pt in chartData.points" :key="pt.index" class="pt-group">
                    <circle
                      :cx="pt.x"
                      :cy="pt.y"
                      :r="pt.isCurrent ? 5.5 : 4"
                      class="pt-circle"
                      :class="{ current: pt.isCurrent }"
                    />
                    <text :x="pt.x" :y="chartData.svgHeight - 10" text-anchor="middle" class="xl">
                      {{ pt.label }}
                    </text>
                    <!-- Hit target for tooltip hover -->
                    <circle
                      :cx="pt.x"
                      :cy="pt.y"
                      r="14"
                      fill="transparent"
                      class="pt-hit"
                      tabindex="0"
                      :aria-label="`${pt.label}: PAC ${formatPac(pt.pac)}, Luas ${pt.areaPct.toFixed(2)}%`"
                      @mouseenter="
                        hoveredPoint = {
                          visitIndex: pt.index,
                          date: pt.date,
                          pac: pt.pac,
                          areaPct: pt.areaPct,
                          x: pt.x,
                          y: pt.y,
                        }
                      "
                      @mouseleave="hoveredPoint = null"
                      @focus="
                        hoveredPoint = {
                          visitIndex: pt.index,
                          date: pt.date,
                          pac: pt.pac,
                          areaPct: pt.areaPct,
                          x: pt.x,
                          y: pt.y,
                        }
                      "
                      @blur="hoveredPoint = null"
                    />
                  </g>
                </svg>

                <!-- Tooltip floating -->
                <div
                  v-if="hoveredPoint"
                  class="chart-tooltip"
                  :style="{ left: `${hoveredPoint.x}px`, top: `${hoveredPoint.y - 10}px` }"
                  role="tooltip"
                >
                  <strong>Kunjungan ke-{{ hoveredPoint.visitIndex }} ({{ hoveredPoint.date }})</strong>
                  <span>PAC: {{ formatPac(hoveredPoint.pac) }}</span>
                  <span>Luas Aₜ: {{ hoveredPoint.areaPct.toFixed(2) }}%</span>
                </div>
              </div>
              <div class="chart-leg">
                <span><i class="leg-line"></i> Garis tren PAC</span>
                <span><i class="leg-zero"></i> Garis baseline (0%)</span>
              </div>
            </section>
          </div>
        </div>

        <!-- Dual-Audience Narrative Tabs (Only for Final Follow-Up Visits) -->
        <section
          v-if="!isBaseline && (visit.clinician_notes || visit.patient_narrative)"
          id="tabs-card"
          class="panel tabs-card"
          aria-labelledby="tabs-heading"
        >
          <h2 id="tabs-heading" class="sr">Narasi Evaluasi Longitudinal</h2>
          <div class="tablist" role="tablist" aria-label="Narasi hasil pemeriksaan">
            <button
              id="tab-patient"
              class="tab"
              role="tab"
              :aria-selected="activeTab === 'patient'"
              :class="{ active: activeTab === 'patient' }"
              aria-controls="panel-patient"
              type="button"
              @click="activeTab = 'patient'"
            >
              Ringkasan Pasien
            </button>
            <button
              id="tab-clinician"
              class="tab"
              role="tab"
              :aria-selected="activeTab === 'clinician'"
              :class="{ active: activeTab === 'clinician' }"
              aria-controls="panel-clinician"
              type="button"
              @click="activeTab = 'clinician'"
            >
              Catatan Klinisi
            </button>
          </div>

          <div
            v-if="activeTab === 'patient'"
            id="panel-patient"
            class="tabpanel"
            role="tabpanel"
            aria-labelledby="tab-patient"
          >
            <p id="patient-narrative-text">{{ visit.patient_narrative }}</p>
            <div class="source">
              <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3Z" />
                <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" />
              </svg>
              <div>
                <p>
                  <strong>Sumber:</strong>
                  <span id="narrative-source-tag">
                    {{
                      visit.narrative_source === 'llm'
                        ? 'llm (Google Gemini API · temperature: 0.3 · Factual Grounding)'
                        : 'template_fallback (Templat Deterministik Tabel 3.5 Proposal)'
                    }}
                  </span>
                </p>
                <p class="source-sub">
                  Narasi dibuat otomatis sebagai asisten dokumentasi visual, bukan penilaian klinis mandiri.
                </p>
              </div>
            </div>
          </div>

          <div
            v-else
            id="panel-clinician"
            class="tabpanel"
            role="tabpanel"
            aria-labelledby="tab-clinician"
          >
            <p id="clinician-notes-text">{{ visit.clinician_notes }}</p>
            <div class="source">
              <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3Z" />
                <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" />
              </svg>
              <div>
                <p>
                  <strong>Sumber:</strong>
                  <span>
                    {{
                      visit.narrative_source === 'llm'
                        ? 'llm (Google Gemini API · temperature: 0.3 · Factual Grounding)'
                        : 'template_fallback (Templat Deterministik Tabel 3.5 Proposal)'
                    }}
                  </span>
                </p>
                <p class="source-sub">
                  Dokumentasi catatan klinis longitudinal dengan kepatuhan angka Tabel 3.4.
                </p>
              </div>
            </div>
          </div>
        </section>

        <!-- Actions Bar -->
        <div id="actions-bar" class="actions" :class="{ sticky: visit.status === 'draft' }">
          <div class="hint">
            <template v-if="visit.status === 'draft'">
              Periksa batas masker segmentasi dengan teliti sebelum melakukan konfirmasi.
            </template>
            <template v-else>
              Hasil kunjungan ini telah tersimpan dalam rekam medis longitudinal.
            </template>
          </div>

          <div class="btn-row">
            <template v-if="visit.status === 'draft'">
              <button
                id="btn-discard"
                class="btn btn-secondary"
                type="button"
                :disabled="isDiscarding || isConfirming"
                @click="openDiscardModal"
              >
                Foto Ulang
              </button>
              <button
                id="btn-confirm-save"
                class="btn btn-primary"
                type="button"
                :disabled="isDiscarding || isConfirming"
                @click="openSaveModal"
              >
                Simpan Final
              </button>
            </template>
            <template v-else>
              <RouterLink class="btn btn-secondary" to="/">Kembali ke Beranda</RouterLink>
              <RouterLink class="btn btn-primary" to="/pemeriksaan">Pemeriksaan Baru</RouterLink>
            </template>
          </div>
        </div>

        <div class="disclaimer">
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8h.01M11 12h1v4h1" />
          </svg>
          <p>
            Hasil segmentasi dan pengukuran merupakan alat bantu dokumentasi serta pemantauan visual.
            Hasil tidak dimaksudkan sebagai pengganti penilaian klinis tenaga medis.
          </p>
        </div>
      </template>
    </main>

    <!-- Modal Konfirmasi dan Simpan -->
    <div v-if="showSaveModal" id="modal-save" class="modal-back">
      <div
        class="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="ms-title"
        aria-describedby="ms-desc"
      >
        <h2 id="ms-title">Konfirmasi dan simpan hasil?</h2>
        <p id="ms-desc">
          Hasil kunjungan ke-{{ visitDisplayNumber }} ({{ formatDateID(visit?.visit_date) }}) akan
          dikonfirmasi dan disimpan sebagai rekam kunjungan final pasien {{ patient?.id || visit?.patient_id }}.
          Setelah disimpan, hasil menjadi bagian dari riwayat pasien.
        </p>

        <div class="check" :class="{ invalid: maskCheckboxError }">
          <input id="chk-mask" v-model="maskConfirmed" type="checkbox" aria-describedby="chk-err" />
          <label for="chk-mask">
            Saya telah memeriksa kesesuaian batas masker segmentasi dengan luka fisik.
          </label>
        </div>
        <p v-if="maskCheckboxError" id="chk-err" class="err" role="alert">
          {{ maskCheckboxError }}
        </p>

        <div class="btns">
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="isConfirming"
            @click="showSaveModal = false"
          >
            Batal
          </button>
          <button
            id="btn-do-save"
            class="btn btn-primary"
            type="button"
            :disabled="isConfirming"
            @click="handleConfirmSave"
          >
            {{ isConfirming ? 'Menyimpan...' : 'Konfirmasi dan Simpan' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal Foto Ulang / Buang Draf -->
    <div v-if="showDiscardModal" id="modal-discard" class="modal-back">
      <div
        class="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="md-title"
        aria-describedby="md-desc"
      >
        <h2 id="md-title">Foto ulang / buang draf?</h2>
        <p id="md-desc">
          Draf hasil kunjungan ke-{{ visitDisplayNumber }} belum tersimpan dan akan dibuang. Pilih ini jika
          batas masker segmentasi tidak sesuai dengan luka fisik. Anda akan diarahkan kembali ke
          halaman Unggah Foto untuk mengambil foto ulang. Data pasien dan kunjungan lain tidak terpengaruh.
        </p>

        <div class="btns">
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="isDiscarding"
            @click="showDiscardModal = false"
          >
            Batal
          </button>
          <button
            id="btn-do-discard"
            class="btn btn-danger"
            type="button"
            :disabled="isDiscarding"
            @click="handleDiscardDraft"
          >
            {{ isDiscarding ? 'Membuang...' : 'Buang Draf dan Foto Ulang' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.h4-page {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
}

.skip-link {
  position: absolute;
  left: 16px;
  top: -80px;
  z-index: 100;
  background: var(--navy);
  color: #fff;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 6px;
  transition: top var(--dur);
}
.skip-link:focus {
  top: 10px;
}

.topbar {
  min-height: 64px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.topbar-in {
  min-height: 64px;
  max-width: 1120px;
  margin: auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}
.brand-mark {
  width: 32px;
  height: 32px;
  border: 1px solid var(--navy);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--navy);
  font-weight: 600;
  font-size: 18px;
  flex: none;
}
.brand-name {
  display: block;
  font-size: 16px;
  font-weight: 650;
  color: var(--navy);
  line-height: 1.2;
}
.brand-sub {
  display: block;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.2;
}
.topright {
  display: flex;
  align-items: center;
  gap: 20px;
}
.sys {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-2);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
  flex: none;
}
.dot.offline {
  background: var(--error);
}
.topnav {
  display: flex;
  height: 64px;
  gap: 4px;
}
.topnav a {
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 14px;
  color: var(--text-2);
  text-decoration: none;
  position: relative;
  transition: color var(--dur);
}
.topnav a:hover {
  color: var(--navy);
}
.topnav a[aria-current='page'] {
  color: var(--navy);
  font-weight: 650;
}
.topnav a[aria-current='page']::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 2px;
  background: var(--teal);
}

.main-container {
  max-width: 1120px;
  margin: 0 auto;
  padding: 20px 24px 72px;
}
.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 14px;
  min-height: 40px;
}
.crumb a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--teal);
  font-weight: 600;
  text-decoration: none;
}
.crumb a:hover {
  text-decoration: underline;
}
.crumb span {
  color: var(--muted);
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin: 4px 0 16px;
}
h1 {
  font-size: 28px;
  line-height: 1.2;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--navy);
  margin: 0;
}
.visit-meta {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text-2);
  font-size: 14px;
}
.chip {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 650;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid;
}
.chip.draft {
  color: var(--amber);
  background: var(--amber-bg);
  border-color: var(--amber-bd);
}
.chip.final {
  color: var(--green);
  background: var(--green-bg);
  border-color: var(--green-bd);
}
.chip.base {
  color: var(--navy);
  background: var(--teal-soft);
  border-color: var(--teal);
}

.patient {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--teal);
  border-radius: var(--radius);
  padding: 12px 18px;
  display: flex;
  gap: 10px 28px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.p-main {
  font-size: 15px;
  color: var(--text);
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.rm {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 18px;
  color: var(--navy);
}
.p-main span + span::before {
  content: '·';
  margin-right: 10px;
  color: var(--border-strong);
}
.p-loc {
  font-size: 14px;
  color: var(--text-2);
}

.banner {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 18px;
  border: 1px solid;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.55;
  margin-bottom: 20px;
}
.banner-icon {
  width: 20px;
  height: 20px;
  margin-top: 1px;
  flex: none;
}
.banner strong {
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}
.banner p {
  margin: 0;
}
.banner.draft {
  background: var(--amber-bg);
  border-color: var(--amber-bd);
  color: var(--amber);
}
.banner.final {
  background: var(--green-bg);
  border-color: var(--green-bd);
  color: var(--green);
}
.banner.base {
  background: var(--teal-soft);
  border-color: var(--teal);
  color: var(--navy);
}

.error-banner {
  background: var(--error-bg);
  border: 1px solid #fca5a5;
  border-radius: var(--radius);
  padding: 14px 18px;
  color: #7f1d1d;
  font-size: 14px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.error-banner strong {
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}
.error-banner p {
  margin: 0;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 24px;
  align-items: start;
}
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.viz {
  padding: 18px 20px 16px;
}
.viz-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.viz-head h2 {
  font-size: 16px;
  font-weight: 650;
  margin: 0;
  color: var(--navy);
}
.viz-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.toggle-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-2);
  cursor: pointer;
}
.toggle-wrap input {
  accent-color: var(--teal);
  cursor: pointer;
}
.legend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-2);
}
.sw {
  width: 16px;
  height: 12px;
  background: rgba(34, 197, 94, 0.35);
  border: 2px solid #16a34a;
  border-radius: 3px;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.fig {
  margin: 0;
}
.fig-label {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 14px;
  font-weight: 650;
  margin-bottom: 8px;
  color: var(--navy);
}
.fig-label small {
  font-weight: 500;
  color: var(--muted);
  font-size: 12px;
}
.img-box {
  width: 100%;
  aspect-ratio: 4/3;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #f1f5f9;
  overflow: hidden;
  display: grid;
  place-items: center;
}
.img-box img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.viz-note {
  margin-top: 12px;
  font-size: 12px;
  color: var(--muted);
}

.metrics {
  display: grid;
  gap: 16px;
}
.metric {
  padding: 18px 20px;
}
.m-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.m-value {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-size: 40px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--navy);
  letter-spacing: -0.02em;
  margin-top: 6px;
}
.m-value.trend-menurun {
  color: var(--green);
}
.m-value.trend-meningkat {
  color: #b91c1c;
}
.m-value.trend-stabil {
  color: #b45309;
}

.m-sub {
  font-size: 13px;
  color: var(--text-2);
  margin-top: 4px;
}
.delta-sub {
  font-size: 13px;
  color: var(--muted);
  margin-top: 2px;
}
.trend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  padding: 6px 12px;
  border-radius: 12px;
  border: 1px solid;
}
.trend.trend-menurun {
  color: var(--green);
  background: var(--green-bg);
  border-color: var(--green-bd);
}
.trend.trend-meningkat {
  color: #b91c1c;
  background: #fee2e2;
  border-color: #fca5a5;
}
.trend.trend-stabil {
  color: #b45309;
  background: #fef3c7;
  border-color: #fcd34d;
}
.trend svg {
  width: 14px;
  height: 14px;
}

.pac-zero-box {
  margin-top: 10px;
  padding: 10px 14px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-2);
}
.pac-zero-box strong {
  display: block;
  color: var(--navy);
  margin-bottom: 2px;
}

.m-limit {
  font-size: 12px;
  color: var(--muted);
  margin-top: 10px;
  line-height: 1.5;
}
.m-note {
  font-size: 13px;
  color: var(--text-2);
  margin-top: 12px;
  line-height: 1.6;
}

/* Chart */
.chart {
  padding: 16px 18px 14px;
}
.chart h2 {
  font-size: 15px;
  font-weight: 650;
  color: var(--navy);
  margin: 0;
}
.chart .sub {
  font-size: 12px;
  color: var(--muted);
  margin: 2px 0 0;
}
.chart-wrap {
  position: relative;
  margin-top: 10px;
}
.chart svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}
.zero-line {
  stroke: #94a3b8;
  stroke-width: 1.25;
}
.chart-zero-lbl {
  font-size: 10.5px;
  fill: var(--muted);
  font-family: var(--mono);
}
.chart-line {
  fill: none;
  stroke: var(--teal);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.pt-circle {
  fill: var(--navy);
  stroke: #fff;
  stroke-width: 2;
  transition: r var(--dur);
}
.pt-circle.current {
  fill: var(--teal);
}
.xl {
  font-size: 11px;
  fill: var(--text-2);
  font-weight: 600;
  font-family: var(--sans);
}
.pt-hit {
  cursor: pointer;
  outline: none;
}
.pt-hit:hover + .pt-circle,
.pt-hit:focus + .pt-circle {
  r: 7;
}

.chart-tooltip {
  position: absolute;
  transform: translate(-50%, -100%);
  background: var(--navy);
  color: #fff;
  font-size: 12px;
  line-height: 1.45;
  padding: 6px 10px;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.25);
  pointer-events: none;
  white-space: nowrap;
  z-index: 10;
}
.chart-tooltip strong {
  display: block;
}
.chart-tooltip span {
  display: block;
  color: #e2e8f0;
}
.chart-leg {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-2);
}
.chart-leg span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.leg-line {
  display: inline-block;
  width: 18px;
  height: 0;
  border-top: 2.5px solid var(--teal);
}
.leg-zero {
  display: inline-block;
  width: 18px;
  height: 0;
  border-top: 1.5px solid #94a3b8;
}

/* Tabs */
.tabs-card {
  margin-top: 24px;
}
.tablist {
  display: flex;
  gap: 28px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
}
.tab {
  font: inherit;
  font-size: 15px;
  color: var(--text-2);
  background: none;
  border: 0;
  padding: 14px 2px;
  margin-bottom: -1px;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  min-height: 48px;
  transition: color var(--dur), border-color var(--dur);
}
.tab:hover {
  color: var(--navy);
}
.tab.active {
  color: var(--navy);
  font-weight: 650;
  border-bottom-color: var(--teal);
}
.tabpanel {
  padding: 20px 22px 22px;
}
.tabpanel p {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text);
  max-width: 880px;
  margin: 0;
}
.source {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 10px;
  align-items: flex-start;
  max-width: 880px;
}
.source svg {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  color: var(--teal);
  flex: none;
}
.source p {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-2);
  margin: 0;
}
.source-sub {
  margin-top: 2px !important;
  color: var(--muted) !important;
}

/* Actions */
.actions {
  margin-top: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 16px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.actions.sticky {
  position: sticky;
  bottom: 12px;
  z-index: 20;
  box-shadow: 0 8px 24px rgba(15, 41, 66, 0.14);
}
.actions .hint {
  font-size: 13px;
  color: var(--text-2);
  max-width: 480px;
}
.btn-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 18px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  transition: background-color var(--dur), border-color var(--dur);
}
.btn-primary {
  background: var(--navy);
  color: #fff;
}
.btn-primary:hover {
  background: var(--navy-hover);
}
.btn-secondary {
  background: var(--surface);
  color: var(--navy);
  border-color: var(--border-strong);
}
.btn-secondary:hover {
  border-color: var(--navy);
  background: var(--bg);
}
.btn-danger {
  background: var(--error);
  color: #fff;
}
.btn-danger:hover {
  background: #991b1b;
}

.disclaimer {
  margin-top: 20px;
  background: #f1f5f9;
  border: 1px solid var(--border-strong);
  color: #334155;
  border-radius: var(--radius);
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.6;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.disclaimer svg {
  width: 16px;
  height: 16px;
  margin-top: 3px;
  flex: none;
}
.disclaimer p {
  margin: 0;
}

/* Modal */
.modal-back {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 50;
}
.modal {
  background: #fff;
  border-radius: 10px;
  max-width: 480px;
  width: 100%;
  padding: 24px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}
.modal h2 {
  font-size: 18px;
  color: var(--navy);
  margin: 0 0 8px;
}
.modal p {
  font-size: 14px;
  color: var(--text-2);
  line-height: 1.6;
  margin: 0;
}
.modal .btns {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
  flex-wrap: wrap;
}
.check {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 16px;
  padding: 14px 16px;
  background: var(--teal-soft);
  border: 1px solid #bfdcdc;
  border-radius: 8px;
}
.check.invalid {
  background: #fef2f2;
  border-color: #fecaca;
}
.check input {
  flex: none;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  accent-color: var(--navy);
  cursor: pointer;
}
.check label {
  font-size: 14px;
  line-height: 1.5;
  font-weight: 500;
  color: var(--text);
  cursor: pointer;
}
.err {
  margin-top: 8px;
  font-size: 13px;
  color: var(--error);
  font-weight: 500;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--teal);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 40px auto 16px;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.loading-state {
  text-align: center;
  color: var(--muted);
}

@media (max-width: 1000px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 760px) {
  .pair {
    grid-template-columns: 1fr;
  }
  .actions {
    flex-direction: column;
    align-items: stretch;
  }
  .btn-row {
    flex-direction: column-reverse;
  }
  .btn-row .btn {
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  * {
    animation: none !important;
    transition: none !important;
  }
}
</style>
