<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import PacFinalCard from '@/components/PacFinalCard.vue'
import PacPreviewCard from '@/components/PacPreviewCard.vue'
import NarrativeTabs from '@/components/NarrativeTabs.vue'
import RulerCalibration from '@/components/RulerCalibration.vue'
import VisitActionModals from '@/components/VisitActionModals.vue'
import { formatDateID, formatDecimalID } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()

const visitId = computed(() => Number(route.params.visitId))

const serverOnline = ref<boolean | null>(null)
const healthLabel = ref('Server Lokal Terhubung')

const visit = ref<VisitRecord | null>(null)
const patient = ref<PatientSummary | null>(null)
const finalVisits = ref<VisitRecord[]>([])
const isLoading = ref(true)
const loadError = ref('')
const showMaskOverlay = ref(true)

const isDraft = computed(() => visit.value?.status === 'draft')
const isCalibrated = computed(
  () => visit.value?.measure_mode === 'calibrated' && visit.value?.area_cm2 !== null,
)

const isBaselineVisit = computed(() => {
  if (!visit.value) return false
  if (visit.value.status === 'draft') {
    return visit.value.preview ? visit.value.preview.is_baseline : finalVisits.value.length === 0
  }
  return visit.value.visit_index === 1
})

const displayVisitNumber = computed(() => {
  if (!visit.value) return 1
  if (visit.value.visit_index !== null) return visit.value.visit_index
  return finalVisits.value.length + 1
})

const statusChipLabel = computed(() => {
  if (!visit.value) return ''
  return visit.value.status === 'draft' ? 'Belum disimpan' : 'Tersimpan'
})

const statusChipClass = computed(() => {
  if (!visit.value || visit.value.status === 'draft') return 'draft'
  return isBaselineVisit.value ? 'base' : 'final'
})

const guidanceBanner = computed(() => {
  if (!visit.value) return null
  if (isDraft.value) {
    return {
      cls: 'draft',
      text: 'Periksa garis hijau batas luka pada foto, lalu pilih Setujui dan Simpan.',
    }
  }
  if (isBaselineVisit.value) {
    return {
      cls: 'base',
      text: 'Ini pemeriksaan awal. Perubahan luas tersedia mulai pemeriksaan kedua.',
    }
  }
  return null
})

const patientAttrs = computed(() => {
  const p = patient.value
  if (!p) return []
  const items: string[] = []
  if (p.umur !== null && p.umur !== undefined) items.push(`${p.umur} tahun`)
  if (p.jk) items.push(p.jk)
  return items
})

const baselineFinalVisit = computed<VisitRecord | null>(
  () => finalVisits.value.find((v) => v.visit_index === 1) ?? finalVisits.value[0] ?? null,
)

const originalImageUrl = computed(() => resolveStorageUrl(visit.value?.image_path))
const segmentationDisplayUrl = computed(() => {
  if (!visit.value) return ''
  if (!showMaskOverlay.value) return resolveStorageUrl(visit.value.image_path)
  return resolveStorageUrl(visit.value.overlay_path || visit.value.image_path)
})

const baselinePhotoDisplayUrl = computed(() => {
  const base = baselineFinalVisit.value
  if (!base) return ''
  if (!showMaskOverlay.value) return resolveStorageUrl(base.image_path)
  return resolveStorageUrl(base.overlay_path || base.image_path)
})

const woundPixelsText = computed(() => {
  const n = visit.value?.n_wound_px ?? 0
  return Math.round(n).toLocaleString('id-ID')
})

const toastMessage = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined

const showSaveModal = ref(false)
const showDiscardModal = ref(false)
const saveModalError = ref('')
const discardModalError = ref('')
const isConfirming = ref(false)
const isDiscarding = ref(false)

const saveOpenerRef = ref<HTMLButtonElement | null>(null)
const discardOpenerRef = ref<HTMLButtonElement | null>(null)
let lastModalOpener: HTMLButtonElement | null = null

const saveModalDescription = computed(() => {
  if (!visit.value) return ''
  if (isBaselineVisit.value) {
    return `Pemeriksaan pertama (${formatDateID(visit.value.visit_date)}) akan disimpan sebagai acuan awal pasien ${visit.value.patient_id}.`
  }
  return `Hasil kunjungan ke-${displayVisitNumber.value} (${formatDateID(visit.value.visit_date)}) dan perhitungan perubahan luas akan disimpan ke riwayat pasien ${visit.value.patient_id}.`
})

function showToast(msg: string) {
  toastMessage.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMessage.value = '' }, 4500)
}

function handleVisitUpdated(updated: VisitRecord) {
  visit.value = updated
}

function handleCalibrationConflict(msg: string) {
  showToast(msg)
  loadPageData()
}

function openSaveModal() {
  if (!isDraft.value) return
  lastModalOpener = saveOpenerRef.value
  saveModalError.value = ''
  showSaveModal.value = true
}

function openDiscardModal() {
  if (!isDraft.value) return
  lastModalOpener = discardOpenerRef.value
  discardModalError.value = ''
  showDiscardModal.value = true
}

function closeModals() {
  if (isConfirming.value || isDiscarding.value) return
  showSaveModal.value = false
  showDiscardModal.value = false
  nextTick(() => lastModalOpener?.focus())
}

async function handleConfirmAndSave() {
  if (!visit.value || isConfirming.value) return

  saveModalError.value = ''
  isConfirming.value = true
  try {
    const confirmZero = visit.value.n_wound_px <= 0 || visit.value.area_pct <= 0
    const confirmed = await confirmVisit(visit.value.id, confirmZero)
    visit.value = confirmed
    showSaveModal.value = false
    showToast('Hasil pemeriksaan berhasil disimpan.')
    try {
      finalVisits.value = await fetchPatientVisits(confirmed.patient_id, 'final')
    } catch {
      // Abaikan jika pemuatan ulang daftar final gagal; kunjungan utama sudah tersimpan
    }
  } catch (err) {
    saveModalError.value =
      err instanceof ApiError ? err.message : 'Terjadi kesalahan saat menyimpan kunjungan.'
  } finally {
    isConfirming.value = false
  }
}

async function handleDiscardAndRetake() {
  if (!visit.value || isDiscarding.value) return
  discardModalError.value = ''
  isDiscarding.value = true
  const targetPatientId = visit.value.patient_id
  try {
    await deleteVisit(visit.value.id)
    showDiscardModal.value = false
    await router.push(`/pemeriksaan/${encodeURIComponent(targetPatientId)}/unggah`)
  } catch (err) {
    discardModalError.value =
      err instanceof ApiError ? err.message : 'Gagal menghapus pemeriksaan yang belum disimpan.'
    isDiscarding.value = false
  }
}

async function loadPageData() {
  if (!Number.isFinite(visitId.value) || visitId.value <= 0) {
    loadError.value = 'ID kunjungan tidak valid.'
    isLoading.value = false
    return
  }

  isLoading.value = true
  loadError.value = ''

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
    const [p, finals] = await Promise.all([
      fetchPatient(v.patient_id),
      fetchPatientVisits(v.patient_id, 'final'),
    ])
    patient.value = p
    finalVisits.value = finals
  } catch (err) {
    loadError.value = err instanceof ApiError ? err.message : 'Gagal memuat detail kunjungan.'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => loadPageData())
onBeforeUnmount(() => { if (toastTimer) clearTimeout(toastTimer) })
watch(() => route.params.visitId, () => loadPageData())
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
        <RouterLink
          :to="visit ? `/pemeriksaan/${encodeURIComponent(visit.patient_id)}/unggah` : '/pemeriksaan'"
        >
          <span aria-hidden="true">←</span>
          {{ visit ? 'Kembali ke Unggah Foto' : 'Kembali ke Pilih Pasien' }}
        </RouterLink>
        <template v-if="visit">
          <span aria-hidden="true">/</span>
          <RouterLink
            v-if="!isDraft"
            :to="`/pasien/${encodeURIComponent(visit.patient_id)}`"
          >
            Riwayat {{ visit.patient_id }}
          </RouterLink>
          <span v-else>{{ visit.patient_id }}</span>
          <span aria-hidden="true">/</span>
          <span aria-current="page">Kunjungan ke-{{ displayVisitNumber }}</span>
        </template>
      </nav>

      <div class="title-row">
        <div>
          <h1>Hasil Pemeriksaan Luka</h1>
          <div v-if="visit" class="visit-meta">
            <span id="visitMeta">
              Kunjungan ke-{{ displayVisitNumber }} · {{ formatDateID(visit.visit_date) }}
            </span>
            <span id="chip" class="chip" :class="statusChipClass">{{ statusChipLabel }}</span>
          </div>
        </div>
      </div>

      <div v-if="loadError" id="load-error-banner" class="error-banner" role="alert">
        <div>
          <strong>Gagal memuat data kunjungan</strong>
          <p>{{ loadError }}</p>
        </div>
        <button id="btn-retry-load" class="btn btn-primary" type="button" @click="loadPageData">
          Coba lagi
        </button>
      </div>

      <div v-else-if="isLoading" class="panel metric" role="status">
        Memuat detail hasil pemeriksaan...
      </div>

      <template v-else-if="visit">
        <section class="patient" aria-label="Informasi pasien">
          <div class="p-main">
            <span class="rm">{{ visit.patient_id }}</span>
            <span v-if="patient?.nama">{{ patient.nama }}</span>
            <span v-for="(attr, idx) in patientAttrs" :key="idx">{{ attr }}</span>
          </div>
          <div v-if="patient?.lokasi" class="p-loc">
            Lokasi ulkus: <b>{{ patient.lokasi }}</b>
          </div>
        </section>

        <div v-if="guidanceBanner" id="bannerBox">
          <div class="banner" :class="guidanceBanner.cls" role="status">
            <span>{{ guidanceBanner.text }}</span>
          </div>
        </div>

        <div class="layout">
          <div>
            <section class="panel viz" aria-labelledby="t-viz">
              <div class="viz-head">
                <div class="viz-title-row">
                  <h2 id="t-viz">Foto dan Batas Luka</h2>
                  <details class="info-pop">
                    <summary aria-label="Info piksel foto">?</summary>
                    <div class="info-pop-body" role="note">
                      Terdeteksi {{ woundPixelsText }} piksel luka dari 65.536 piksel foto
                      (256×256).
                    </div>
                  </details>
                </div>
                <div class="viz-controls">
                  <div class="legend">
                    <span class="sw" aria-hidden="true"></span>
                    <span>Batas luka (garis hijau)</span>
                  </div>
                  <label class="overlay-toggle" for="toggle-mask-overlay">
                    <input id="toggle-mask-overlay" v-model="showMaskOverlay" type="checkbox" />
                    <span>Tampilkan garis luka</span>
                  </label>
                </div>
              </div>

              <div v-if="!isBaselineVisit" class="pair">
                <figure id="figAwal" class="fig">
                  <div class="fig-label">Pemeriksaan pertama (Awal)</div>
                  <div class="fig-frame">
                    <img
                      v-if="baselinePhotoDisplayUrl"
                      id="imgBaseline"
                      :src="baselinePhotoDisplayUrl"
                      alt="Foto luka pada pemeriksaan pertama sebagai pembanding awal"
                    />
                    <span v-else class="m-sub">Foto awal tidak tersedia</span>
                  </div>
                </figure>
                <figure id="figSekarang" class="fig">
                  <div class="fig-label">Sekarang (Kunjungan ke-{{ displayVisitNumber }})</div>
                  <div class="fig-frame">
                    <img
                      v-if="segmentationDisplayUrl"
                      id="imgSegmentation"
                      :src="segmentationDisplayUrl"
                      alt="Foto luka pemeriksaan sekarang dengan garis hijau batas luka"
                    />
                    <span v-else class="m-sub">Foto pemeriksaan tidak tersedia</span>
                  </div>
                </figure>
              </div>

              <div v-else class="pair">
                <figure class="fig">
                  <div class="fig-label">Foto Asli</div>
                  <div class="fig-frame">
                    <img
                      v-if="originalImageUrl"
                      id="imgOriginal"
                      :src="originalImageUrl"
                      alt="Foto asli luka pada pemeriksaan pertama"
                    />
                    <span v-else class="m-sub">Foto asli tidak tersedia</span>
                  </div>
                </figure>
                <figure class="fig">
                  <div class="fig-label">Batas Luka</div>
                  <div class="fig-frame">
                    <img
                      v-if="segmentationDisplayUrl"
                      id="imgSegmentation"
                      :src="segmentationDisplayUrl"
                      alt="Foto luka dengan garis hijau batas luka"
                    />
                    <span v-else class="m-sub">Foto batas luka tidak tersedia</span>
                  </div>
                </figure>
              </div>
            </section>

            <RulerCalibration
              v-if="isDraft"
              :visit="visit"
              :image-url="originalImageUrl"
              @updated="handleVisitUpdated"
              @conflict="handleCalibrationConflict"
              @notify="showToast"
            />
          </div>

          <div class="metrics">
            <PacPreviewCard
              v-if="isDraft && visit.preview"
              :preview="visit.preview"
              :baseline-visit="baselineFinalVisit"
              :current-area-pct="visit.area_pct"
              :current-area-cm2="visit.area_cm2"
            />
            <PacFinalCard
              v-else-if="!isDraft"
              :visit="visit"
              :baseline-visit="baselineFinalVisit"
            />

            <section v-if="isBaselineVisit" class="panel metric" aria-labelledby="m1">
              <div class="m-head">
                <div id="m1" class="m-label">Luas luka</div>
                <span id="modeBadge" class="modebadge" :class="isCalibrated ? 'cal' : 'rel'">
                  {{ isCalibrated ? 'Terkalibrasi cm²' : 'Dari foto' }}
                </span>
              </div>
              <div id="areaVal" class="m-value">
                {{
                  isCalibrated && visit.area_cm2 !== null
                    ? `${formatDecimalID(visit.area_cm2, 1)} cm²`
                    : `${formatDecimalID(visit.area_pct, 1)}%`
                }}
              </div>
              <div id="areaSub" class="m-sub">
                {{
                  isCalibrated
                    ? `setara ${formatDecimalID(visit.area_pct, 1)}% dari luas foto`
                    : 'dari luas foto'
                }}
              </div>
              <div
                v-if="isCalibrated && visit.scale_cm_per_px !== null"
                id="areaScale"
                class="m-sub m-scale"
              >
                Skala {{ formatDecimalID(visit.scale_cm_per_px, 4) }} cm/px<template
                  v-if="visit.calib_length_cm !== null"
                >
                  (penggaris {{ formatDecimalID(visit.calib_length_cm, 1) }} cm)
                </template>
              </div>
            </section>
          </div>
        </div>

        <NarrativeTabs
          v-if="!isDraft"
          :visit="visit"
          :is-baseline="isBaselineVisit"
          @notify="showToast"
        />

        <div v-if="isDraft" id="actions" class="actions">
          <div class="btn-row">
            <button
              id="bDiscard"
              ref="discardOpenerRef"
              class="btn btn-secondary"
              type="button"
              @click="openDiscardModal"
            >
              Foto Ulang
            </button>
            <button
              id="bSave"
              ref="saveOpenerRef"
              class="btn btn-primary"
              type="button"
              @click="openSaveModal"
            >
              Setujui dan Simpan
            </button>
          </div>
        </div>

        <div v-else id="actions" class="actions">
          <div class="btn-row">
            <RouterLink id="btnNextPatient" class="btn btn-secondary" to="/pemeriksaan">
              Pasien berikutnya
            </RouterLink>
            <RouterLink
              id="btnHistory"
              class="btn btn-primary"
              :to="`/pasien/${encodeURIComponent(visit.patient_id)}`"
            >
              Lihat riwayat
            </RouterLink>
          </div>
        </div>

        <div class="disclaimer">
          <p>Hasil ini merupakan estimasi dari foto, bukan diagnosis medis.</p>
        </div>
      </template>
    </main>

    <VisitActionModals
      :show-save="showSaveModal"
      :show-discard="showDiscardModal"
      :save-description="saveModalDescription"
      :visit-number="displayVisitNumber"
      :is-confirming="isConfirming"
      :is-discarding="isDiscarding"
      :save-error="saveModalError"
      :discard-error="discardModalError"
      @close="closeModals"
      @confirm-save="handleConfirmAndSave"
      @confirm-discard="handleDiscardAndRetake"
    />

    <div aria-live="polite">
      <div v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</div>
    </div>
  </div>
</template>

<style scoped src="../assets/h4_hasil.css"></style>
