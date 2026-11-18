<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  ApiError,
  checkServerHealth,
  deletePatient,
  deleteVisit,
  fetchPatient,
  fetchPatientVisits,
} from '@/api/patients'
import PatientDangerModals from '@/components/PatientDangerModals.vue'
import TrendChart from '@/components/TrendChart.vue'
import VisitHistoryTable from '@/components/VisitHistoryTable.vue'
import type { PatientSummary, VisitRecord } from '@/types/patient'
import { formatDateID, formatDecimalID, formatSignedDecimalID } from '@/utils/formatters'
import { sortVisitsChronologically } from '@/utils/trendChart'
import { getTrendCssClass } from '@/utils/visitWarnings'

const route = useRoute()
const router = useRouter()
const patientId = computed(() => String(route.params.patientId ?? '').trim())

const serverOnline = ref<boolean | null>(null)
const healthLabel = ref('Memeriksa server...')

const patient = ref<PatientSummary | null>(null)
const finalVisits = ref<VisitRecord[]>([])
const isLoading = ref(true)
const loadError = ref('')

const visitToDelete = ref<VisitRecord | null>(null)
const showDeletePatientModal = ref(false)
const isDeletingVisit = ref(false)
const isDeletingPatient = ref(false)
const deleteVisitError = ref('')
const deletePatientError = ref('')
const deletePatientBtnRef = ref<HTMLButtonElement | null>(null)
let lastModalOpener: HTMLElement | null = null

const toastMessage = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined

const sortedVisits = computed(() => sortVisitsChronologically(finalVisits.value))
const baselineVisit = computed<VisitRecord | null>(() => sortedVisits.value[0] ?? null)
const latestVisit = computed<VisitRecord | null>(() =>
  sortedVisits.value.length > 0 ? sortedVisits.value[sortedVisits.value.length - 1] ?? null : null,
)
const previousBeforeLatest = computed<VisitRecord | null>(() =>
  sortedVisits.value.length >= 2 ? sortedVisits.value[sortedVisits.value.length - 2] ?? null : null,
)

const patientAttrs = computed(() => {
  const p = patient.value
  if (!p) return []
  const out: string[] = []
  if (p.umur !== null && p.umur !== undefined) out.push(`${p.umur} tahun`)
  if (p.jk) out.push(p.jk)
  return out
})

function formatVisitArea(v: VisitRecord | null): string {
  if (!v) return '–'
  if (v.measure_mode === 'calibrated' && v.area_cm2 !== null) {
    return `${formatDecimalID(v.area_cm2)} cm²`
  }
  return `${formatDecimalID(v.area_pct)}%`
}

const pacBadgeClass = computed(() => {
  if (!latestVisit.value) return ''
  const cls = getTrendCssClass(latestVisit.value.trend_status)
  if (cls === 'up') return 'neg'
  if (cls === 'flat') return 'flat'
  return ''
})

const pacSummaryDelta = computed(() => {
  const v = latestVisit.value
  if (!v || v.delta_area === null || v.delta_area === undefined) return ''
  const unit = v.pac_basis === 'calibrated' ? 'cm²' : 'pp'
  const basisLabel = v.pac_basis === 'calibrated' ? 'Basis cm²' : 'Basis Relatif %'
  return `${basisLabel} · ΔA ${formatSignedDecimalID(v.delta_area, 2)} ${unit} vs A₀`
})

function showToast(msg: string) {
  toastMessage.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMessage.value = '' }, 5000)
}

function openDeleteVisitModal(visit: VisitRecord) {
  lastModalOpener = document.activeElement as HTMLElement | null
  deleteVisitError.value = ''
  visitToDelete.value = visit
}

function openDeletePatientModal() {
  lastModalOpener = deletePatientBtnRef.value
  deletePatientError.value = ''
  showDeletePatientModal.value = true
}

function closeModals() {
  if (isDeletingVisit.value || isDeletingPatient.value) return
  visitToDelete.value = null
  showDeletePatientModal.value = false
  nextTick(() => {
    if (lastModalOpener && document.contains(lastModalOpener)) {
      lastModalOpener.focus()
    }
  })
}

async function handleConfirmDeleteVisit() {
  const target = visitToDelete.value
  if (!target || isDeletingVisit.value) return
  const deletedNum = target.visit_index ?? sortedVisits.value.length
  const prev = previousBeforeLatest.value
  deleteVisitError.value = ''
  isDeletingVisit.value = true
  try {
    await deleteVisit(target.id)
    visitToDelete.value = null
    await loadPageData()
    const msg = prev
      ? `Kunjungan ke-${deletedNum} dihapus. Kunjungan ke-${prev.visit_index ?? deletedNum - 1} kini menjadi data terkini.`
      : `Kunjungan ke-${deletedNum} (baseline) dihapus. Riwayat kunjungan pasien kini kosong.`
    showToast(msg)
  } catch (err) {
    deleteVisitError.value =
      err instanceof ApiError ? err.message : 'Gagal menghapus kunjungan terakhir.'
  } finally {
    isDeletingVisit.value = false
  }
}

async function handleConfirmDeletePatient() {
  if (!patient.value || isDeletingPatient.value) return
  deletePatientError.value = ''
  isDeletingPatient.value = true
  try {
    await deletePatient(patient.value.id)
    showDeletePatientModal.value = false
    await router.push('/pemeriksaan')
  } catch (err) {
    deletePatientError.value =
      err instanceof ApiError ? err.message : 'Gagal menghapus data pasien.'
  } finally {
    isDeletingPatient.value = false
  }
}

async function loadPageData() {
  if (!patientId.value) {
    loadError.value = 'Kode pasien tidak valid.'
    isLoading.value = false
    return
  }

  isLoading.value = true
  loadError.value = ''

  checkServerHealth()
    .then((h) => {
      serverOnline.value = h.status === 'ok'
      healthLabel.value = h.status === 'ok' ? 'Server terhubung' : 'Server tidak terhubung'
    })
    .catch(() => {
      serverOnline.value = false
      healthLabel.value = 'Server tidak terhubung'
    })

  try {
    const [p, visits] = await Promise.all([
      fetchPatient(patientId.value),
      fetchPatientVisits(patientId.value, 'final'),
    ])
    patient.value = p
    finalVisits.value = visits
    document.title = `Riwayat ${p.id} · WoundAI`
  } catch (err) {
    loadError.value = err instanceof ApiError ? err.message : 'Gagal memuat riwayat pasien.'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => loadPageData())
onBeforeUnmount(() => { if (toastTimer) clearTimeout(toastTimer) })
watch(() => route.params.patientId, () => loadPageData())
</script>

<template>
  <div class="h5-page">
    <a class="skip-link" href="#main-content">Lewati ke konten utama</a>

    <header class="topbar">
      <div class="topbar-in">
        <RouterLink class="brand" to="/" aria-label="WoundAI, ke Beranda">
          <span class="brand-mark" aria-hidden="true">+</span>
          <span>
            <span class="brand-name">WoundAI</span>
            <span class="brand-sub">Pemantauan Ulkus Kusta</span>
          </span>
        </RouterLink>
        <div class="topright">
          <div class="sys" role="status">
            <span class="dot" :class="{ offline: serverOnline === false }" aria-hidden="true"></span>
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
        <RouterLink to="/pemeriksaan">Pemeriksaan</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ patient?.id || patientId }}</span>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Riwayat</span>
      </nav>

      <div class="head">
        <div>
          <h1>Riwayat Pasien</h1>
          <p>Pantau lintasan perubahan luas luka dan detail pengukuran antarkunjungan.</p>
        </div>
        <RouterLink
          id="btnNewVisit"
          class="btn btn-primary"
          :to="`/pemeriksaan/${encodeURIComponent(patientId)}/unggah`"
        >
          Tambah Kunjungan
        </RouterLink>
      </div>

      <div v-if="loadError" id="load-error-banner" class="error-banner" role="alert">
        <div>
          <strong>Gagal memuat riwayat pasien</strong>
          <p>{{ loadError }}</p>
        </div>
        <button class="btn btn-primary" type="button" @click="loadPageData">Coba lagi</button>
      </div>

      <div v-else-if="isLoading" class="card overview" role="status">
        Memuat riwayat pemeriksaan pasien...
      </div>

      <template v-else-if="patient">
        <section id="overview" class="card overview" aria-labelledby="ov-name">
          <div class="ov-top">
            <div>
              <div class="name-row">
                <h2 id="ov-name" class="name">{{ patient.nama || 'Pasien Tanpa Inisial' }}</h2>
                <span class="rm">{{ patient.id }}</span>
              </div>
              <div v-if="patientAttrs.length" class="demog">{{ patientAttrs.join(' · ') }}</div>
              <div v-if="patient.lokasi" class="dx">
                Lokasi ulkus: <b>{{ patient.lokasi }}</b>
              </div>
            </div>

            <dl class="ov-meta">
              <div>
                <dt>Riwayat</dt>
                <dd><b>{{ sortedVisits.length }} kunjungan</b> tersimpan</dd>
              </div>
              <div>
                <dt>Kunjungan terakhir</dt>
                <dd>
                  <b>{{ latestVisit ? formatDateID(latestVisit.visit_date) : 'Belum ada' }}</b>
                </dd>
              </div>
              <div>
                <dt>Status terkini</dt>
                <dd><b>{{ patient.trend_status }}</b></dd>
              </div>
            </dl>
          </div>

          <div v-if="sortedVisits.length > 0" class="stats">
            <div class="stat">
              <div class="s-label">Baseline A₀</div>
              <div id="statBaselineVal" class="s-val">{{ formatVisitArea(baselineVisit) }}</div>
              <div class="s-sub">
                {{ formatDateID(baselineVisit?.visit_date) }}
                · {{ baselineVisit?.measure_mode === 'calibrated' ? 'Terkalibrasi cm²' : 'Basis Relatif %' }}
              </div>
            </div>

            <div class="stat">
              <div class="s-label">Luas Saat Ini</div>
              <div id="statLatestVal" class="s-val">{{ formatVisitArea(latestVisit) }}</div>
              <div class="s-sub">
                {{ formatDateID(latestVisit?.visit_date) }}
                · {{ latestVisit?.measure_mode === 'calibrated' ? 'Terkalibrasi cm²' : 'Basis Relatif %' }}
              </div>
            </div>

            <div class="stat">
              <div class="s-label">Total Perubahan (PAC)</div>
              <template v-if="sortedVisits.length === 1">
                <div class="pac-na">Belum tersedia</div>
                <div class="s-sub">PAC dihitung mulai kunjungan kedua</div>
              </template>
              <template v-else-if="!latestVisit || latestVisit.pac === null">
                <div class="pac-na">Tidak dapat dihitung</div>
                <div class="s-sub">Baseline A₀ bernilai 0,00%</div>
              </template>
              <template v-else>
                <div id="statPacVal" class="pac-badge" :class="pacBadgeClass">
                  {{ formatSignedDecimalID(latestVisit.pac, 1) }}%
                </div>
                <div class="s-sub">{{ pacSummaryDelta }}</div>
              </template>
            </div>
          </div>
        </section>

        <TrendChart :visits="sortedVisits" :patient-id="patient.id" />

        <VisitHistoryTable
          :visits="sortedVisits"
          :allow-delete="true"
          @request-delete="openDeleteVisitModal"
        />

        <section id="dangerZone" class="danger" aria-labelledby="t-danger">
          <div>
            <h2 id="t-danger">Zona Bahaya</h2>
            <p>Tindakan di area ini bersifat permanen dan mempengaruhi seluruh rekam medis pasien.</p>
          </div>
          <button
            id="bDelPatient"
            ref="deletePatientBtnRef"
            class="btn btn-danger-o"
            type="button"
            @click="openDeletePatientModal"
          >
            Hapus Seluruh Data Pasien
          </button>
        </section>
      </template>
    </main>

    <PatientDangerModals
      v-if="patient"
      :patient="patient"
      :visit-to-delete="visitToDelete"
      :previous-visit="previousBeforeLatest"
      :visit-count="sortedVisits.length"
      :show-patient-modal="showDeletePatientModal"
      :is-deleting-visit="isDeletingVisit"
      :is-deleting-patient="isDeletingPatient"
      :visit-error="deleteVisitError"
      :patient-error="deletePatientError"
      @close="closeModals"
      @confirm-delete-visit="handleConfirmDeleteVisit"
      @confirm-delete-patient="handleConfirmDeletePatient"
    />

    <div aria-live="polite">
      <div v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</div>
    </div>
  </div>
</template>

<style scoped src="../assets/h5_riwayat.css"></style>
