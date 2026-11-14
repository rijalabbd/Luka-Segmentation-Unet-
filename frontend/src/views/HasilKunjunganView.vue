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
const healthLabel = ref('Server Lokal Terhubung · Data Terisolasi')

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
  if (visit.value.status === 'draft') return 'Draf — Belum Disimpan'
  return isBaselineVisit.value ? 'Final · Baseline' : 'Final — Tersimpan'
})

const statusChipClass = computed(() => {
  if (!visit.value || visit.value.status === 'draft') return 'draft'
  return isBaselineVisit.value ? 'base' : 'final'
})

const bannerInfo = computed(() => {
  if (!visit.value) return { cls: 'draft', title: '', text: '' }
  if (visit.value.status === 'draft') {
    return {
      cls: 'draft',
      title: 'Draf — Belum Disimpan',
      text: 'Hasil pemeriksaan masih berupa draf dan belum disimpan ke riwayat pasien. Periksa kembali batas masker segmentasi. Jika foto memuat penggaris sebidang luka, kalibrasi opsional tersedia di bawah foto. Jika masker tidak sesuai dengan luka, pilih Foto Ulang.',
    }
  }
  if (isBaselineVisit.value) {
    return {
      cls: 'base',
      title: 'Baseline — Kunjungan Pertama',
      text: 'Kunjungan pertama digunakan sebagai baseline (A₀). Perhitungan PAC baru tersedia mulai kunjungan kedua.',
    }
  }
  return {
    cls: 'final',
    title: 'Final — Terkonfirmasi dan Tersimpan',
    text: 'Hasil pemeriksaan telah dikonfirmasi dan tersimpan sebagai rekam kunjungan pasien.',
  }
})

const patientAttrs = computed(() => {
  const p = patient.value
  if (!p) return []
  const items: string[] = []
  if (p.umur !== null && p.umur !== undefined) items.push(`${p.umur} tahun`)
  if (p.jk) items.push(p.jk)
  return items
})

const originalImageUrl = computed(() => resolveStorageUrl(visit.value?.image_path))
const segmentationDisplayUrl = computed(() => {
  if (!visit.value) return ''
  if (!showMaskOverlay.value) return resolveStorageUrl(visit.value.image_path)
  return resolveStorageUrl(visit.value.overlay_path || visit.value.image_path)
})

const baselineFinalVisit = computed<VisitRecord | null>(
  () => finalVisits.value.find((v) => v.visit_index === 1) ?? finalVisits.value[0] ?? null,
)

const toastMessage = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined

const showSaveModal = ref(false)
const showDiscardModal = ref(false)
const chkMaskChecked = ref(false)
const saveModalError = ref('')
const discardModalError = ref('')
const isConfirming = ref(false)
const isDiscarding = ref(false)

const modalsRef = ref<InstanceType<typeof VisitActionModals> | null>(null)
const saveOpenerRef = ref<HTMLButtonElement | null>(null)
const discardOpenerRef = ref<HTMLButtonElement | null>(null)
let lastModalOpener: HTMLButtonElement | null = null

const saveModalDescription = computed(() => {
  if (!visit.value) return ''
  const modeTxt = isCalibrated.value ? 'terkalibrasi (cm²)' : 'berbasis luas relatif (%)'
  const mixedNote =
    isCalibrated.value && visit.value.preview?.pac_basis === 'relative'
      ? ', dengan PAC memakai luas relatif karena kunjungan awal tidak terkalibrasi'
      : ''
  return (
    `Hasil kunjungan ke-${displayVisitNumber.value} (${formatDateID(visit.value.visit_date)}) ` +
    `akan dikonfirmasi dan disimpan sebagai rekam kunjungan final pasien ${visit.value.patient_id} ` +
    `dengan pengukuran ${modeTxt}${mixedNote}. Setelah disimpan, hasil dan kalibrasi tidak dapat diubah.`
  )
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
  chkMaskChecked.value = false
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
  if (!chkMaskChecked.value) {
    saveModalError.value = 'Centang pernyataan ini setelah memeriksa masker, lalu simpan.'
    modalsRef.value?.focusCheckbox()
    return
  }

  saveModalError.value = ''
  isConfirming.value = true
  try {
    const confirmZero = visit.value.n_wound_px <= 0 || visit.value.area_pct <= 0
    const confirmed = await confirmVisit(visit.value.id, confirmZero)
    visit.value = confirmed
    showSaveModal.value = false
    showToast('Hasil kunjungan berhasil dikonfirmasi dan disimpan.')
    try {
      finalVisits.value = await fetchPatientVisits(confirmed.patient_id, 'final')
    } catch {
      // Abaikan jika pemuatan ulang daftar final gagal; kunjungan utama sudah tersimpan
    }
  } catch (err) {
    saveModalError.value = err instanceof ApiError ? err.message : 'Terjadi kesalahan saat mengonfirmasi kunjungan.'
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
    discardModalError.value = err instanceof ApiError ? err.message : 'Gagal membuang draf kunjungan.'
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
watch(chkMaskChecked, (val) => { if (val) saveModalError.value = '' })
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

        <div id="bannerBox">
          <div class="banner" :class="bannerInfo.cls" role="status">
            <div>
              <b>{{ bannerInfo.title }}</b>
              <span>{{ bannerInfo.text }}</span>
            </div>
          </div>
        </div>

        <div class="layout">
          <div>
            <section class="panel viz" aria-labelledby="t-viz">
              <div class="viz-head">
                <h2 id="t-viz">Foto Asli dan Hasil Segmentasi</h2>
                <div class="viz-controls">
                  <div class="legend">
                    <span class="sw" aria-hidden="true"></span>
                    <span>Area luka (masker segmentasi)</span>
                  </div>
                  <label class="overlay-toggle" for="toggle-mask-overlay">
                    <input id="toggle-mask-overlay" v-model="showMaskOverlay" type="checkbox" />
                    <span>Tampilkan overlay masker</span>
                  </label>
                </div>
              </div>

              <div class="pair">
                <figure class="fig">
                  <div class="fig-label">Foto Asli <small>Sebelum segmentasi</small></div>
                  <div class="fig-frame">
                    <img
                      v-if="originalImageUrl"
                      id="imgOriginal"
                      :src="originalImageUrl"
                      alt="Foto asli luka sebelum overlay segmentasi"
                    />
                    <span v-else class="m-sub">Citra asli tidak tersedia</span>
                  </div>
                </figure>
                <figure class="fig">
                  <div class="fig-label">
                    Hasil Segmentasi
                    <small>{{ showMaskOverlay ? 'Foto dengan overlay masker' : 'Overlay disembunyikan' }}</small>
                  </div>
                  <div class="fig-frame">
                    <img
                      v-if="segmentationDisplayUrl"
                      id="imgSegmentation"
                      :src="segmentationDisplayUrl"
                      alt="Hasil segmentasi luka dengan overlay masker hijau transparan pada area luka"
                    />
                    <span v-else class="m-sub">Citra segmentasi tidak tersedia</span>
                  </div>
                </figure>
              </div>
              <p class="viz-note">
                Estimasi visual berbasis segmentasi otomatis ({{ visit.n_wound_px }} piksel luka dari
                65.536 piksel peta masker 256×256).
              </p>
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
            <section class="panel metric" aria-labelledby="m1">
              <div class="m-head">
                <div id="m1" class="m-label">Estimasi Luas Area Luka</div>
                <span id="modeBadge" class="modebadge" :class="isCalibrated ? 'cal' : 'rel'">
                  {{ isCalibrated ? 'Terkalibrasi · cm²' : 'Basis Relatif · %' }}
                </span>
              </div>
              <div id="areaVal" class="m-value">
                {{
                  isCalibrated && visit.area_cm2 !== null
                    ? `${formatDecimalID(visit.area_cm2)} cm²`
                    : `${formatDecimalID(visit.area_pct)}%`
                }}
              </div>
              <div id="areaSub" class="m-sub">
                {{
                  isCalibrated
                    ? `setara ${formatDecimalID(visit.area_pct)}% dari luas citra`
                    : 'Persentase area luka pada citra'
                }}
              </div>
              <div
                v-if="isCalibrated && visit.scale_cm_per_px !== null"
                id="areaScale"
                class="m-sub m-scale"
              >
                Skala s = {{ formatDecimalID(visit.scale_cm_per_px, 4) }} cm/px<template
                  v-if="visit.calib_length_cm !== null"
                >
                  (penggaris {{ formatDecimalID(visit.calib_length_cm, 1) }} cm)
                </template>
              </div>
              <p id="areaLimit" class="m-limit">
                {{
                  isCalibrated
                    ? 'Luas dihitung dari kalibrasi penggaris dua titik pada bidang penggaris. Tidak mengoreksi perbedaan sudut pandang.'
                    : 'Estimasi relatif terhadap luas citra (% kanvas), tanpa penanda kalibrasi fisik. Bukan ukuran dalam cm².'
                }}
              </p>
              <p v-if="!isDraft && isBaselineVisit" id="baseNote" class="m-note">
                Hasil ini menjadi acuan baseline A₀. Nilai PAC dan grafik tren baru tersedia
                mulai kunjungan kedua.
              </p>
            </section>

            <PacPreviewCard
              v-if="isDraft && visit.preview"
              :preview="visit.preview"
              :baseline-visit="baselineFinalVisit"
            />
            <PacFinalCard
              v-else-if="!isDraft"
              :visit="visit"
              :baseline-visit="baselineFinalVisit"
            />
          </div>
        </div>

        <section v-if="isDraft" id="narrWait" class="panel narr-wait">
          <b>Narasi dibuat setelah hasil dikonfirmasi.</b> Catatan klinis dan ringkasan pasien
          disusun setelah hasil dikonfirmasi dan disimpan.
        </section>

        <NarrativeTabs
          v-else
          :visit="visit"
          :is-baseline="isBaselineVisit"
          @notify="showToast"
        />

        <div v-if="isDraft" id="actions" class="actions sticky">
          <p class="hint">
            Periksa batas masker segmentasi pada foto. Jika sesuai, setujui dan simpan. Jika memilih
            Foto Ulang, draf beserta kalibrasi pada kunjungan ini akan dibuang.
          </p>
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
          <p class="hint">Hasil ini sudah dikonfirmasi dan tersimpan dalam riwayat pasien.</p>
          <div class="btn-row">
            <RouterLink
              class="btn btn-primary"
              :to="`/pasien/${encodeURIComponent(visit.patient_id)}`"
            >
              Lihat Riwayat Pasien
            </RouterLink>
          </div>
        </div>

        <div class="disclaimer">
          <p>
            Hasil segmentasi dan pengukuran merupakan alat bantu dokumentasi serta pemantauan
            visual. Hasil tidak dimaksudkan sebagai pengganti penilaian klinis tenaga medis.
          </p>
        </div>
      </template>
    </main>

    <VisitActionModals
      ref="modalsRef"
      v-model:chk-mask="chkMaskChecked"
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
