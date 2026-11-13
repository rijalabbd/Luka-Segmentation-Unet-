<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  ApiError,
  checkServerHealth,
  createDraftVisit,
  deleteVisit,
  fetchDemoSamplePhoto,
  fetchPatient,
  fetchPatientVisits,
  resolveStorageUrl,
} from '@/api/patients'
import type { PatientSummary, VisitRecord } from '@/types/patient'

const route = useRoute()
const router = useRouter()

const patientId = computed(() => String(route.params.patientId ?? '').trim())
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

const serverOnline = ref<boolean | null>(null)
const healthLabel = ref('Server Lokal Terhubung · Data Terisolasi')

const patient = ref<PatientSummary | null>(null)
const finalVisits = ref<VisitRecord[]>([])
const pendingDraft = ref<VisitRecord | null>(null)
const isDiscardingDraft = ref(false)
const isLoadingPatient = ref(true)
const loadError = ref('')
const submitError = ref('')

function getTodayISO(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const todayISO = getTodayISO()
const visitDate = ref(todayISO)

const selectedFile = ref<File | null>(null)
const previewUrl = ref('')
const fileError = ref('')
const isDragging = ref(false)
const isConfirmed = ref(false)
const isLoadingSample = ref(false)
const isSubmitting = ref(false)
const liveAnnouncement = ref('')
const isZoomOpen = ref(false)

// Panel foto acuan state (10.3)
const activeRefTab = ref<'baseline' | 'latest'>('baseline')
const showRefContour = ref(false)
const compareMode = ref<'side' | 'overlay'>('side')
const overlayOpacity = ref(50)

const fileInputRef = ref<HTMLInputElement | null>(null)
const pickBtnRef = ref<HTMLButtonElement | null>(null)
const replaceBtnRef = ref<HTMLButtonElement | null>(null)

const nextVisitNumber = computed(() => finalVisits.value.length + 1)
const isFollowUp = computed(() => nextVisitNumber.value >= 2)

const baselineVisit = computed<VisitRecord | null>(() => {
  if (!finalVisits.value.length) return null
  return finalVisits.value[0] ?? null
})

const latestFinalVisit = computed<VisitRecord | null>(() => {
  if (!finalVisits.value.length) return null
  return finalVisits.value[finalVisits.value.length - 1] ?? null
})

const hasDistinctLatestRef = computed(() => {
  return (
    finalVisits.value.length >= 2 &&
    baselineVisit.value !== null &&
    latestFinalVisit.value !== null &&
    baselineVisit.value.id !== latestFinalVisit.value.id
  )
})

const activeRefVisit = computed<VisitRecord | null>(() => {
  if (!isFollowUp.value) return null
  if (activeRefTab.value === 'latest' && hasDistinctLatestRef.value) {
    return latestFinalVisit.value
  }
  return baselineVisit.value
})

const activeRefImageUrl = computed(() => {
  if (!activeRefVisit.value?.image_path) return ''
  return resolveStorageUrl(activeRefVisit.value.image_path)
})

const activeRefOverlayUrl = computed(() => {
  if (!activeRefVisit.value?.overlay_path) return ''
  return resolveStorageUrl(activeRefVisit.value.overlay_path)
})

const activeRefDisplayUrl = computed(() => {
  if (showRefContour.value && activeRefOverlayUrl.value) {
    return activeRefOverlayUrl.value
  }
  return activeRefImageUrl.value
})

const latestFinalDate = computed(() => latestFinalVisit.value?.visit_date ?? '')

const MONTHS_SHORT = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'Mei',
  'Jun',
  'Jul',
  'Agu',
  'Sep',
  'Okt',
  'Nov',
  'Des',
]

function formatDateID(isoDate: string | null | undefined): string {
  if (!isoDate) return '-'
  const parts = isoDate.split('-').map(Number)
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return isoDate
  const [y, m, d] = parts
  const monthName = MONTHS_SHORT[(m ?? 1) - 1] ?? ''
  return `${String(d).padStart(2, '0')} ${monthName} ${y}`
}

const visitBadgeText = computed(() => {
  if (!isFollowUp.value) {
    return 'Kunjungan awal (baseline)'
  }
  const lastDateStr = latestFinalDate.value
    ? formatDateID(latestFinalDate.value)
    : (patient.value?.terakhir ?? '-')
  return `Kunjungan ke-${nextVisitNumber.value} · Kunjungan terakhir: ${lastDateStr}`
})

const patientAttrs = computed(() => {
  const p = patient.value
  if (!p) return []
  const items: string[] = []
  if (p.umur !== null && p.umur !== undefined) items.push(`${p.umur} tahun`)
  if (p.jk) items.push(p.jk)
  if (p.lokasi) items.push(p.lokasi)
  return items
})

const dateError = computed(() => {
  if (!visitDate.value) return 'Isi tanggal pemeriksaan.'
  if (visitDate.value > todayISO) {
    return 'Tanggal pemeriksaan tidak boleh melebihi hari ini.'
  }
  if (latestFinalDate.value && visitDate.value < latestFinalDate.value) {
    return `Tanggal pemeriksaan tidak boleh lebih awal dari kunjungan terakhir (${formatDateID(latestFinalDate.value)}).`
  }
  return ''
})

const isDateValid = computed(() => dateError.value === '')

const canRunDetection = computed(() => {
  return (
    selectedFile.value !== null &&
    isDateValid.value &&
    isConfirmed.value &&
    !isSubmitting.value &&
    !loadError.value
  )
})

const statusReasonText = computed(() => {
  if (isSubmitting.value) return 'Mohon tunggu, jangan tutup halaman ini.'
  if (!selectedFile.value) {
    return isFollowUp.value
      ? 'Unggah foto luka terlebih dahulu, lalu bandingkan dengan foto acuan.'
      : 'Unggah foto luka terlebih dahulu untuk menjalankan deteksi.'
  }
  if (!isDateValid.value) return dateError.value
  if (!isConfirmed.value) return 'Centang konfirmasi jarak dan sudut foto untuk melanjutkan.'
  return 'Foto siap diproses.'
})

const confirmLabelText = computed(() => {
  return isFollowUp.value
    ? 'Saya sudah membandingkan foto dengan foto acuan; jarak dan sudut sudah sama.'
    : 'Foto diambil sesuai panduan di samping.'
})

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

function isAllowedImageFile(file: File): boolean {
  const mime = (file.type || '').toLowerCase()
  const ext = file.name.toLowerCase().split('.').pop() ?? ''
  if (mime === 'image/jpeg' || mime === 'image/png') return true
  if (!mime && (ext === 'jpg' || ext === 'jpeg' || ext === 'png')) return true
  return false
}

function handleSelectedFile(file: File | null | undefined) {
  if (!file) return
  submitError.value = ''
  if (!isAllowedImageFile(file)) {
    fileError.value = 'Berkas harus berupa gambar berformat JPG atau PNG.'
    return
  }
  if (file.size > MAX_FILE_SIZE) {
    fileError.value = 'Ukuran berkas melebihi 10 MB. Pilih foto yang lebih kecil.'
    return
  }
  if (file.size === 0) {
    fileError.value = 'Berkas foto luka tidak boleh kosong.'
    return
  }

  revokePreview()
  previewUrl.value = URL.createObjectURL(file)
  selectedFile.value = file
  fileError.value = ''
  liveAnnouncement.value = `Foto ${file.name} berhasil dimuat.`
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function onDropzoneKeydown(e: KeyboardEvent) {
  if (e.target !== e.currentTarget) return
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    openFilePicker()
  }
}

function onFileInputChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  handleSelectedFile(file)
}

function clearPhoto() {
  revokePreview()
  selectedFile.value = null
  isConfirmed.value = false
  fileError.value = ''
  submitError.value = ''
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
  pickBtnRef.value?.focus()
}

function onDropzoneDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDropzoneDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
}

function onDropzoneDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  handleSelectedFile(file)
}

async function loadDemoSamplePhoto() {
  if (!patient.value?.is_demo || isLoadingSample.value) return
  isLoadingSample.value = true
  fileError.value = ''
  submitError.value = ''
  try {
    const sampleFile = await fetchDemoSamplePhoto(patientId.value)
    handleSelectedFile(sampleFile)
  } catch (err) {
    if (err instanceof ApiError) {
      fileError.value = err.message
    } else {
      fileError.value = 'Gagal memuat foto sampel dari server backend.'
    }
  } finally {
    isLoadingSample.value = false
  }
}

async function handleDiscardDraft() {
  if (!pendingDraft.value || isDiscardingDraft.value) return
  isDiscardingDraft.value = true
  submitError.value = ''
  try {
    await deleteVisit(pendingDraft.value.id)
    pendingDraft.value = null
    liveAnnouncement.value = 'Draf lama telah dibuang. Silakan unggah foto baru.'
    pickBtnRef.value?.focus()
  } catch (err) {
    if (err instanceof ApiError) {
      submitError.value = err.message
    } else {
      submitError.value = 'Gagal membuang draf kunjungan.'
    }
  } finally {
    isDiscardingDraft.value = false
  }
}

async function handleRunDetection() {
  if (!canRunDetection.value || !selectedFile.value) return
  isSubmitting.value = true
  fileError.value = ''
  submitError.value = ''
  liveAnnouncement.value = 'Menganalisis area luka.'

  try {
    const createdVisit = await createDraftVisit(
      patientId.value,
      visitDate.value,
      selectedFile.value,
      isConfirmed.value,
    )
    pendingDraft.value = null
    liveAnnouncement.value = 'Analisis selesai. Mengalihkan ke halaman hasil kunjungan.'
    await router.push(`/kunjungan/${createdVisit.id}`)
  } catch (err) {
    if (err instanceof ApiError) {
      submitError.value = err.message
    } else {
      submitError.value = 'Terjadi kesalahan saat memproses foto luka.'
    }
    isSubmitting.value = false
  }
}

function handleWindowDragOver(e: DragEvent) {
  e.preventDefault()
}

function handleWindowDrop(e: DragEvent) {
  e.preventDefault()
}

async function loadPageData() {
  isLoadingPatient.value = true
  loadError.value = ''
  submitError.value = ''

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
    const [p, finals, drafts] = await Promise.all([
      fetchPatient(patientId.value),
      fetchPatientVisits(patientId.value, 'final'),
      fetchPatientVisits(patientId.value, 'draft'),
    ])
    patient.value = p
    finalVisits.value = finals
    pendingDraft.value = drafts[0] ?? null
    activeRefTab.value = 'baseline'
    if (finals.length > 0) {
      const lastDate = finals[finals.length - 1]?.visit_date
      if (lastDate && lastDate > visitDate.value) {
        visitDate.value = lastDate
      }
    }
  } catch (err) {
    if (err instanceof ApiError) {
      loadError.value = err.message
    } else {
      loadError.value = 'Gagal memuat data pasien.'
    }
  } finally {
    isLoadingPatient.value = false
  }
}

onMounted(() => {
  window.addEventListener('dragover', handleWindowDragOver)
  window.addEventListener('drop', handleWindowDrop)
  loadPageData()
})

onBeforeUnmount(() => {
  window.removeEventListener('dragover', handleWindowDragOver)
  window.removeEventListener('drop', handleWindowDrop)
  revokePreview()
})
</script>

<template>
  <div class="h3-page">
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
      <RouterLink id="back-link" class="back" to="/pemeriksaan">
        <span aria-hidden="true">←&nbsp;</span>Ganti pasien (Kembali ke Pemilihan Pasien)
      </RouterLink>
      <h1>Unggah Foto dan Deteksi</h1>

      <div v-if="loadError" id="load-error-banner" class="error-banner" role="alert">
        <div>
          <strong>Gagal terhubung ke server atau memuat data pasien</strong>
          <p>{{ loadError }}</p>
        </div>
        <div class="banner-actions">
          <button id="btn-retry-load" class="btn btn-primary" type="button" @click="loadPageData">
            Coba lagi
          </button>
          <RouterLink class="btn btn-secondary" to="/pemeriksaan">
            Pilih Pasien Lain
          </RouterLink>
        </div>
      </div>

      <template v-else>
        <section class="patient" aria-label="Pasien yang diperiksa">
          <div>
            <div class="p-label">Pasien yang diperiksa</div>
            <div class="p-line">
              <span class="p-rm">{{ patient?.id || patientId }}</span>
              <span v-if="patient?.nama" class="p-name">{{ patient.nama }}</span>
            </div>
            <div v-if="patientAttrs.length" class="p-attrs">
              <span v-for="(attr, idx) in patientAttrs" :key="idx">{{ attr }}</span>
            </div>
          </div>
          <p class="p-note">
            Pastikan nomor RM sesuai dengan pasien di hadapan Anda sebelum mengunggah foto.
          </p>
        </section>

        <!-- Peringatan draf yang menggantung (10.2 butir 3) -->
        <section
          v-if="pendingDraft"
          id="draft-warning"
          class="draft-banner"
          role="region"
          aria-label="Peringatan draf belum disimpan"
        >
          <div class="draft-banner-text">
            <strong>Ada draf belum disimpan ({{ formatDateID(pendingDraft.visit_date) }})</strong>
            <p>
              Luas relatif terdeteksi sementara:
              <strong>{{ pendingDraft.area_pct.toFixed(2) }}%</strong> kanvas. Pilih untuk
              melanjutkan evaluasi draf tersebut atau buang draf untuk mengunggah foto baru.
            </p>
          </div>
          <div class="draft-banner-actions">
            <RouterLink
              id="btn-resume-draft"
              class="btn btn-primary"
              :to="`/kunjungan/${pendingDraft.id}`"
            >
              Lanjutkan draf
            </RouterLink>
            <button
              id="btn-discard-draft"
              class="btn btn-secondary"
              type="button"
              :disabled="isDiscardingDraft"
              @click="handleDiscardDraft"
            >
              {{ isDiscardingDraft ? 'Membuang draf...' : 'Buang draf dan unggah baru' }}
            </button>
          </div>
        </section>

        <!-- Banner error saat submit / 422 / 5xx / backend mati (10.1) -->
        <div v-if="submitError" id="submit-error-banner" class="error-banner" role="alert">
          <div>
            <strong>Deteksi tidak dapat diselesaikan</strong>
            <p>{{ submitError }}</p>
          </div>
          <div class="banner-actions">
            <button
              v-if="selectedFile && isDateValid && isConfirmed"
              id="btn-retry-submit"
              class="btn btn-secondary"
              type="button"
              :disabled="isSubmitting"
              @click="handleRunDetection"
            >
              Coba lagi
            </button>
          </div>
        </div>

        <div class="grid" :data-mode="isFollowUp ? '3' : '1'">
          <section class="card" aria-labelledby="t-form">
            <h2 id="t-form" class="sr">Formulir pemeriksaan</h2>
            <div class="status-row">
              <span id="badge" class="badge">{{ visitBadgeText }}</span>
            </div>

            <div class="field">
              <label class="lbl" for="tgl">Tanggal Pemeriksaan</label>
              <input
                id="tgl"
                v-model="visitDate"
                type="date"
                :max="todayISO"
                :min="latestFinalDate || undefined"
                aria-describedby="tgl-hint"
              />
              <p id="tgl-hint" class="hint">
                <template v-if="latestFinalDate">
                  Rentang valid: {{ formatDateID(latestFinalDate) }} s.d. hari ini.
                </template>
                <template v-else>Tidak dapat memilih tanggal setelah hari ini.</template>
              </p>
              <p v-if="dateError" id="tgl-err" class="error" role="alert">{{ dateError }}</p>
            </div>

            <!-- Panel Foto Acuan (10.3) -->
            <section
              v-if="!isFollowUp"
              id="ref-panel-baseline"
              class="ref-panel ref-baseline-only"
              aria-labelledby="ref-baseline-heading"
            >
              <h2 id="ref-baseline-heading" class="ref-title">Foto acuan</h2>
              <p id="ref-baseline-msg" class="ref-baseline-note">
                Kunjungan awal: foto ini akan menjadi acuan kunjungan berikutnya.
              </p>
            </section>

            <section
              v-else
              id="ref-panel"
              class="ref-panel"
              aria-labelledby="ref-title"
            >
              <div class="ref-header">
                <div>
                  <h2 id="ref-title" class="ref-title">Foto acuan</h2>
                  <p class="ref-sub">
                    Alat bantu visual untuk menyamakan jarak dan sudut pemotretan terhadap kunjungan
                    sebelumnya.
                  </p>
                </div>

                <!-- Pilihan tab acuan: Baseline (A0) sebagai utama, Kunjungan Terakhir sebagai tab kedua -->
                <div
                  v-if="hasDistinctLatestRef"
                  class="ref-tabs"
                  role="tablist"
                  aria-label="Pilih foto kunjungan acuan"
                >
                  <button
                    id="tab-ref-baseline"
                    type="button"
                    role="tab"
                    class="ref-tab"
                    :class="{ active: activeRefTab === 'baseline' }"
                    :aria-selected="activeRefTab === 'baseline'"
                    @click="activeRefTab = 'baseline'"
                  >
                    Acuan Utama: Baseline A₀ (Kunjungan ke-1 ·
                    {{ formatDateID(baselineVisit?.visit_date) }})
                  </button>
                  <button
                    id="tab-ref-latest"
                    type="button"
                    role="tab"
                    class="ref-tab"
                    :class="{ active: activeRefTab === 'latest' }"
                    :aria-selected="activeRefTab === 'latest'"
                    @click="activeRefTab = 'latest'"
                  >
                    Kunjungan Terakhir (Kunjungan ke-{{ latestFinalVisit?.visit_index }} ·
                    {{ formatDateID(latestFinalVisit?.visit_date) }})
                  </button>
                </div>
              </div>

              <!-- Keadaan ketika pasien tidak memiliki berkas citra pada kunjungan acuan -->
              <div v-if="!activeRefImageUrl" id="ref-unavailable" class="ref-unavailable" role="status">
                <strong>Foto acuan tidak tersedia</strong>
                <span>
                  Data kunjungan ke-{{ activeRefVisit?.visit_index ?? 1 }} ({{
                    formatDateID(activeRefVisit?.visit_date)
                  }}) tidak menyertakan berkas citra. Gunakan panduan jarak dan sudut di samping.
                </span>
              </div>

              <!-- Keadaan ketika foto acuan tersedia -->
              <div v-else class="ref-body">
                <div class="ref-toolbar">
                  <div class="ref-meta">
                    <span class="ref-tag">
                      {{
                        activeRefTab === 'baseline' || !hasDistinctLatestRef
                          ? 'Baseline A₀'
                          : 'Kunjungan Terakhir'
                      }}
                    </span>
                    <span class="ref-meta-text">
                      Kunjungan ke-{{ activeRefVisit?.visit_index }} ·
                      {{ formatDateID(activeRefVisit?.visit_date) }} · Luas relatif:
                      <strong>{{ activeRefVisit?.area_pct.toFixed(2) }}%</strong>
                    </span>
                  </div>

                  <div class="ref-controls">
                    <label v-if="activeRefOverlayUrl" class="contour-toggle" for="toggle-ref-contour">
                      <input
                        id="toggle-ref-contour"
                        v-model="showRefContour"
                        type="checkbox"
                      />
                      <span>Tampilkan kontur masker acuan</span>
                    </label>
                    <button
                      id="ref-open"
                      type="button"
                      class="btn btn-secondary btn-sm"
                      :aria-label="`Perbesar foto acuan kunjungan ke-${activeRefVisit?.visit_index}`"
                      @click="isZoomOpen = true"
                    >
                      Perbesar
                    </button>
                  </div>
                </div>

                <!-- Jika foto baru belum dipilih: tampilkan foto acuan tunggal -->
                <div v-if="!selectedFile" id="ref-single-view" class="ref-single">
                  <div class="ref-img-box">
                    <img
                      id="ref-img"
                      :src="activeRefDisplayUrl"
                      :alt="`Foto luka acuan dari kunjungan ke-${activeRefVisit?.visit_index}`"
                    />
                  </div>
                  <div class="ref-single-caption">
                    <p>
                      Perhatikan posisi tepi anggota tubuh dan proporsi luka pada bingkai di samping
                      sebelum mengambil atau memilih foto kunjungan baru.
                    </p>
                  </div>
                </div>

                <!-- Jika foto baru sudah dipilih: tampilkan mode Berdampingan atau Tumpuk -->
                <div v-else class="ref-compare">
                  <div class="compare-bar">
                    <span class="compare-lbl">Mode perbandingan visual:</span>
                    <div class="mode-switch" role="group" aria-label="Mode perbandingan visual">
                      <button
                        id="mode-side"
                        type="button"
                        class="mode-btn"
                        :class="{ active: compareMode === 'side' }"
                        :aria-pressed="compareMode === 'side'"
                        @click="compareMode = 'side'"
                      >
                        Berdampingan
                      </button>
                      <button
                        id="mode-overlay"
                        type="button"
                        class="mode-btn"
                        :class="{ active: compareMode === 'overlay' }"
                        :aria-pressed="compareMode === 'overlay'"
                        @click="compareMode = 'overlay'"
                      >
                        Tumpuk
                      </button>
                    </div>
                  </div>

                  <!-- Mode 1: Berdampingan -->
                  <div v-if="compareMode === 'side'" id="ref-side-view" class="ref-side-grid">
                    <figure class="compare-card">
                      <div class="compare-head">
                        <span>Foto Acuan (Kunjungan ke-{{ activeRefVisit?.visit_index }})</span>
                        <small>{{ formatDateID(activeRefVisit?.visit_date) }}</small>
                      </div>
                      <div class="compare-square">
                        <img
                          :src="activeRefDisplayUrl"
                          :alt="`Foto acuan kunjungan ke-${activeRefVisit?.visit_index}`"
                        />
                      </div>
                    </figure>

                    <figure class="compare-card">
                      <div class="compare-head">
                        <span>Foto Baru (Kunjungan ke-{{ nextVisitNumber }})</span>
                        <small>{{ formatDateID(visitDate) }}</small>
                      </div>
                      <div class="compare-square">
                        <img
                          :src="previewUrl"
                          alt="Foto baru yang dipilih untuk dibandingkan"
                        />
                      </div>
                    </figure>
                  </div>

                  <!-- Mode 2: Tumpuk dengan slider transparansi 0-100% -->
                  <div v-else id="ref-overlay-view" class="ref-overlay-wrap">
                    <div class="overlay-stage">
                      <img
                        class="overlay-base"
                        :src="activeRefDisplayUrl"
                        :alt="`Lapisan bawah: foto acuan kunjungan ke-${activeRefVisit?.visit_index}`"
                      />
                      <img
                        class="overlay-top"
                        :src="previewUrl"
                        alt="Lapisan atas: foto kunjungan baru"
                        :style="{ opacity: overlayOpacity / 100 }"
                      />
                    </div>

                    <div class="slider-panel">
                      <div class="slider-head">
                        <label for="opacity-slider">
                          Transparansi foto baru: <strong>{{ overlayOpacity }}%</strong>
                        </label>
                        <span class="slider-sub">
                          Geser untuk menyamakan tepi anggota tubuh dan ukuran bingkai
                        </span>
                      </div>
                      <input
                        id="opacity-slider"
                        v-model.number="overlayOpacity"
                        type="range"
                        min="0"
                        max="100"
                        step="1"
                      />
                      <div class="slider-ticks" aria-hidden="true">
                        <span>0% (Foto acuan)</span>
                        <span>50%</span>
                        <span>100% (Foto baru)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <p class="ref-tip">
                <strong>Tips jarak pemotretan:</strong> Selisih jarak kecil pun menggeser luas
                terbaca (selisih jarak sekitar 2,5% kira-kira menggeser luas sekitar 5%). Panel ini
                adalah alat bantu visual, bukan pengukur jarak otomatis.
              </p>
            </section>

            <label id="foto-lbl" class="lbl" for="file">Foto Luka</label>

            <div
              v-if="!selectedFile"
              id="drop"
              class="drop"
              :class="{ over: isDragging }"
              tabindex="0"
              role="button"
              aria-labelledby="foto-lbl drop-desc"
              @keydown="onDropzoneKeydown"
              @dragenter="onDropzoneDragOver"
              @dragover="onDropzoneDragOver"
              @dragleave="onDropzoneDragLeave"
              @drop="onDropzoneDrop"
            >
              <svg
                viewBox="0 0 48 48"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <rect x="6" y="10" width="36" height="28" rx="4" />
                <circle cx="17" cy="20" r="3.5" />
                <path d="m6 33 10-9 8 7 7-6 11 9" />
                <path d="M36 4v8M32 8h8" />
              </svg>
              <p id="drop-desc">Seret foto ulkus ke area ini atau pilih dari perangkat</p>
              <div class="drop-actions">
                <button
                  id="pick"
                  ref="pickBtnRef"
                  class="btn btn-secondary"
                  type="button"
                  @click.stop="openFilePicker"
                >
                  Pilih Berkas Foto
                </button>
                <button
                  v-if="patient?.is_demo"
                  id="sample"
                  class="btn btn-ghost"
                  type="button"
                  :disabled="isLoadingSample"
                  @click.stop="loadDemoSamplePhoto"
                >
                  {{ isLoadingSample ? 'Memuat Foto Sampel...' : 'Gunakan Foto Sampel (Mode demo)' }}
                </button>
              </div>
              <p class="hint" style="margin: 0">Format gambar (JPG atau PNG), maksimal 10 MB.</p>
            </div>

            <input
              id="file"
              ref="fileInputRef"
              type="file"
              accept="image/jpeg,image/png"
              class="sr"
              tabindex="-1"
              @change="onFileInputChange"
            />

            <p v-if="fileError" id="ferr" class="error" role="alert">{{ fileError }}</p>

            <div v-if="selectedFile" id="preview" class="preview">
              <div class="frame">
                <img
                  id="img"
                  :src="previewUrl"
                  alt="Pratinjau foto luka yang akan diproses"
                />
              </div>
              <div class="fileinfo">
                <div>
                  <div id="fname" class="fname">{{ selectedFile.name }}</div>
                  <div id="fsize" class="fsize">{{ formatFileSize(selectedFile.size) }}</div>
                </div>
                <div class="fileinfo-actions">
                  <span class="fcheck" aria-hidden="true">✓ Foto siap</span>
                  <button
                    id="replace"
                    ref="replaceBtnRef"
                    class="btn btn-secondary"
                    type="button"
                    :disabled="isSubmitting"
                    @click="clearPhoto"
                  >
                    Ganti Foto
                  </button>
                </div>
              </div>
            </div>

            <div id="confirm" class="confirm">
              <input
                id="chk"
                v-model="isConfirmed"
                type="checkbox"
                :disabled="isSubmitting"
              />
              <label id="chk-lbl" for="chk">{{ confirmLabelText }}</label>
            </div>

            <div class="action">
              <p id="reason" class="reason" role="status" aria-live="polite" aria-atomic="true">
                {{ statusReasonText }}
              </p>
              <button
                id="run"
                class="btn btn-primary"
                type="button"
                :disabled="!canRunDetection"
                :aria-busy="isSubmitting"
                aria-describedby="reason"
                @click="handleRunDetection"
              >
                <template v-if="isSubmitting">
                  <span class="spinner" aria-hidden="true"></span>
                  <span>Menganalisis area luka...</span>
                </template>
                <template v-else>
                  <span id="run-txt">Jalankan Deteksi</span>
                </template>
              </button>
            </div>
            <p id="live" class="sr" role="status" aria-live="polite">{{ liveAnnouncement }}</p>
          </section>

          <aside id="guide" class="card guide guide-wrap" aria-labelledby="t-guide">
            <h2 id="t-guide">Panduan Pengambilan Foto</h2>
            <p class="sub">Empat prinsip agar foto antarkunjungan dapat dibandingkan.</p>
            <ol>
              <li>
                <span class="num" aria-hidden="true">1</span>
                <div>
                  <h3>Jarak konsisten</h3>
                  <p>
                    Gunakan jarak yang sama pada setiap kunjungan (misalnya dengan tali atau
                    penggaris pengatur jarak) dan jangan memakai zoom digital.
                  </p>
                </div>
              </li>
              <li>
                <span class="num" aria-hidden="true">2</span>
                <div>
                  <h3>Kamera tegak lurus</h3>
                  <p>Posisikan kamera 90° terhadap permukaan luka.</p>
                </div>
              </li>
              <li>
                <span class="num" aria-hidden="true">3</span>
                <div>
                  <h3>Pencahayaan cukup</h3>
                  <p>Hindari bayangan gelap dan pantulan cahaya.</p>
                </div>
              </li>
              <li>
                <span class="num" aria-hidden="true">4</span>
                <div>
                  <h3>Tanpa filter</h3>
                  <p>Gunakan foto alami tanpa modifikasi warna.</p>
                </div>
              </li>
            </ol>
            <p class="calib">
              <svg
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
                aria-hidden="true"
              >
                <circle cx="10" cy="10" r="7.5" />
                <path d="M10 9v5M10 6.2v.1" />
              </svg>
              <span>
                <strong>Catatan:</strong> Pengukuran luka dihitung relatif terhadap luas citra (%
                kanvas) tanpa penanda kalibrasi fisik.
              </span>
            </p>
          </aside>
        </div>
      </template>
    </main>

    <!-- Dialog perbesar foto acuan -->
    <div
      v-if="isZoomOpen && activeRefDisplayUrl"
      id="zoom"
      class="modal-back"
      @click.self="isZoomOpen = false"
    >
      <div class="modal wide" role="dialog" aria-modal="true" aria-labelledby="z-t">
        <div class="cap">
          <h2 id="z-t">
            Acuan Kunjungan ke-{{ activeRefVisit?.visit_index }} ·
            {{ formatDateID(activeRefVisit?.visit_date) }}
          </h2>
          <button class="btn btn-secondary" type="button" @click="isZoomOpen = false">
            Tutup
          </button>
        </div>
        <img
          id="z-img"
          :src="activeRefDisplayUrl"
          :alt="`Foto luka acuan dari kunjungan ke-${activeRefVisit?.visit_index}, ukuran diperbesar`"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.h3-page {
  --bg: #f8fafc;
  --surface: #ffffff;
  --navy: #0f2942;
  --navy-hover: #163a5f;
  --teal: #2a6f73;
  --teal-soft: #eaf4f4;
  --border: #e2e8f0;
  --border-strong: #cbd5e1;
  --text: #0f172a;
  --text-2: #475569;
  --text-muted: #5b6b80;
  --error: #b91c1c;
  --warn-bg: #fffbeb;
  --warn-border: #d97706;
  --warn-text: #78350f;
  --ok: #166534;
  --radius: 6px;
  --dur: 180ms;

  min-height: 100dvh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.5;
}

.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
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
  border-radius: var(--radius);
  text-decoration: none;
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
  color: inherit;
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
  color: var(--text-muted);
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
  background: var(--ok);
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
  padding: 24px 24px 72px;
}
.back {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  font-size: 14px;
  color: var(--teal);
  font-weight: 600;
  text-decoration: none;
}
.back:hover {
  text-decoration: underline;
}
h1 {
  font-size: 26px;
  line-height: 1.25;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--navy);
  margin: 4px 0 18px;
}

.error-banner {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-left: 4px solid var(--error);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.error-banner strong {
  display: block;
  font-size: 14px;
  color: #991b1b;
  margin-bottom: 2px;
}
.error-banner p {
  margin: 0;
  font-size: 13.5px;
  color: #7f1d1d;
}
.banner-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.draft-banner {
  background: var(--warn-bg);
  border: 1px solid #fde68a;
  border-left: 4px solid var(--warn-border);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.draft-banner-text strong {
  font-size: 14px;
  color: var(--warn-text);
}
.draft-banner-text p {
  margin: 4px 0 0;
  font-size: 13.5px;
  color: var(--warn-text);
  max-width: 600px;
}
.draft-banner-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.patient {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--teal);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.p-label {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 600;
}
.p-line {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 2px 12px;
}
.p-rm {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-size: 24px;
  font-weight: 700;
  color: var(--navy);
  line-height: 1.3;
}
.p-name {
  font-size: 15px;
  font-weight: 600;
}
.p-attrs {
  font-size: 14px;
  color: var(--text-2);
}
.p-attrs span + span::before {
  content: '·';
  margin: 0 8px;
  color: var(--border-strong);
}
.p-note {
  font-size: 13px;
  color: var(--text-muted);
  max-width: 280px;
  margin: 0;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 22px 24px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 650;
  color: var(--teal);
  background: var(--teal-soft);
  padding: 6px 12px;
  border-radius: 999px;
}
label.lbl,
.lbl {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
input[type='date'] {
  height: 44px;
  padding: 0 12px;
  font: inherit;
  font-size: 14px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  min-width: 200px;
}
input[type='date']:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 1px;
  border-color: var(--navy);
}
.field {
  margin-bottom: 20px;
}
.hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 6px 0 0;
}

/* Panel Foto Acuan (10.3) */
.ref-panel {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}
.ref-baseline-only {
  background: var(--teal-soft);
  border-color: #bfdcdc;
}
.ref-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--navy);
  margin: 0;
}
.ref-sub {
  font-size: 13px;
  color: var(--text-2);
  margin: 2px 0 0;
}
.ref-baseline-note {
  margin: 4px 0 0;
  font-size: 13.5px;
  color: var(--navy);
  font-weight: 500;
}
.ref-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}
.ref-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.ref-tab {
  min-height: 38px;
  padding: 6px 12px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  cursor: pointer;
}
.ref-tab.active {
  background: var(--navy);
  color: #fff;
  border-color: var(--navy);
}
.ref-tab:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.ref-unavailable {
  padding: 14px;
  background: var(--surface);
  border: 1px dashed var(--border-strong);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13.5px;
  color: var(--text-2);
}
.ref-unavailable strong {
  color: var(--navy);
}
.ref-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ref-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.ref-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-2);
}
.ref-tag {
  font-size: 11.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--teal);
  background: var(--teal-soft);
  padding: 3px 8px;
  border-radius: 4px;
}
.ref-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.contour-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--navy);
  cursor: pointer;
}
.contour-toggle input {
  width: 18px;
  height: 18px;
  accent-color: var(--navy);
  cursor: pointer;
}
.btn-sm {
  min-height: 36px;
  padding: 0 12px;
  font-size: 13px;
}

.ref-single {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.ref-img-box {
  width: 160px;
  height: 160px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  overflow: hidden;
  background: #0f172a;
  flex: none;
}
.ref-img-box img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.ref-single-caption {
  flex: 1;
  min-width: 200px;
  font-size: 13.5px;
  color: var(--text-2);
}
.ref-single-caption p {
  margin: 0;
}

.ref-compare {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.compare-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.compare-lbl {
  font-size: 13px;
  font-weight: 600;
  color: var(--navy);
}
.mode-switch {
  display: inline-flex;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 2px;
  gap: 2px;
}
.mode-btn {
  min-height: 34px;
  padding: 0 12px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
}
.mode-btn.active {
  background: var(--navy);
  color: #fff;
}
.mode-btn:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 1px;
}

.ref-side-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.compare-card {
  margin: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
}
.compare-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--navy);
}
.compare-head small {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}
.compare-square {
  width: 100%;
  aspect-ratio: 1 / 1;
  max-height: 260px;
  background: #0f172a;
  border-radius: 4px;
  overflow: hidden;
  display: grid;
  place-items: center;
}
.compare-square img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.ref-overlay-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.overlay-stage {
  position: relative;
  width: 100%;
  max-width: 340px;
  aspect-ratio: 1 / 1;
  margin: 0 auto;
  background: #0f172a;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-strong);
}
.overlay-base,
.overlay-top {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.overlay-top {
  transition: opacity 80ms linear;
}
.slider-panel {
  max-width: 420px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.slider-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--navy);
}
.slider-sub {
  font-size: 12px;
  color: var(--text-muted);
}
input[type='range'] {
  width: 100%;
  height: 28px;
  accent-color: var(--navy);
  cursor: pointer;
}
input[type='range']:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
  border-radius: 4px;
}
.slider-ticks {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-2);
  font-weight: 500;
}

.ref-tip {
  margin: 12px 0 0;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 12.5px;
  color: var(--text-2);
  line-height: 1.5;
}

.drop {
  min-height: 220px;
  background: var(--bg);
  border: 1.5px dashed #64748b;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 10px;
  padding: 28px 20px;
  cursor: pointer;
  transition:
    border-color var(--dur),
    background-color var(--dur);
}
.drop:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
  border-color: var(--navy);
}
.drop.over {
  border-color: var(--teal);
  background: var(--teal-soft);
}
.drop svg {
  width: 44px;
  height: 44px;
  color: var(--teal);
}
.drop p {
  font-size: 14px;
  color: var(--text-2);
  max-width: 320px;
  margin: 0;
}
.drop-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 4px;
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
  border-radius: var(--radius);
  border: 1px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  transition:
    background-color var(--dur),
    border-color var(--dur);
}
.btn:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.btn-primary {
  background: var(--navy);
  color: #fff;
}
.btn-primary:hover:not(:disabled) {
  background: var(--navy-hover);
}
.btn-primary:disabled {
  background: #e2e8f0;
  color: #475569;
  border-color: #cbd5e1;
  cursor: not-allowed;
}
.btn-secondary {
  background: var(--surface);
  color: var(--navy);
  border-color: var(--border-strong);
}
.btn-secondary:hover:not(:disabled) {
  border-color: var(--navy);
  background: var(--bg);
}
.btn-ghost {
  background: none;
  color: var(--teal);
  padding: 0 10px;
}
.btn-ghost:hover {
  text-decoration: underline;
}
.error {
  margin-top: 10px;
  font-size: 13px;
  color: var(--error);
  font-weight: 500;
}

.frame {
  background: #0f172a0d;
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  justify-content: center;
  padding: 12px;
}
.frame img {
  display: block;
  max-width: 100%;
  max-height: 360px;
  width: auto;
  height: auto;
  border-radius: 4px;
}
.fileinfo {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.fileinfo-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.fname {
  font-size: 14px;
  font-weight: 600;
  word-break: break-all;
}
.fsize {
  font-size: 13px;
  color: var(--text-muted);
}
.fcheck {
  font-size: 13px;
  color: var(--ok);
  font-weight: 600;
}

.confirm {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 22px;
  padding: 14px 16px;
  background: var(--teal-soft);
  border: 1px solid #bfdcdc;
  border-radius: 8px;
}
.confirm input {
  width: 22px;
  height: 22px;
  margin: 1px 0 0;
  accent-color: var(--navy);
  flex: none;
  cursor: pointer;
}
.confirm label {
  font-size: 14px;
  line-height: 1.5;
  cursor: pointer;
  margin: 0;
  font-weight: 500;
}

.action {
  margin-top: 22px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.reason {
  font-size: 13px;
  color: var(--text-2);
  max-width: 360px;
  margin: 0;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.guide h2 {
  font-size: 16px;
  font-weight: 650;
  color: var(--navy);
  margin: 0 0 4px;
}
.guide .sub {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 14px;
}
.guide ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 14px;
}
.guide li {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
}
.num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--teal-soft);
  color: var(--teal);
  font-weight: 700;
  font-size: 13px;
  display: grid;
  place-items: center;
}
.guide h3 {
  font-size: 14px;
  font-weight: 650;
  margin: 0;
}
.guide li p {
  font-size: 13px;
  color: var(--text-2);
  margin: 2px 0 0;
}
.calib {
  margin: 18px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-2);
}
.calib svg {
  width: 18px;
  height: 18px;
  color: var(--teal);
  margin-top: 1px;
}

.modal-back {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 50;
}
.modal {
  background: #fff;
  border-radius: 10px;
  max-width: 760px;
  width: 100%;
  padding: 18px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}
.modal img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 6px;
  border: 1px solid var(--border);
}
.modal .cap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.modal .cap h2 {
  margin: 0;
  font-size: 16px;
  color: var(--navy);
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation: none;
  }
  .overlay-top,
  .btn,
  .drop,
  .skip-link,
  .topnav a {
    transition: none;
  }
}

@media (max-width: 900px) {
  .grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .grid[data-mode='1'] .guide-wrap {
    order: -1;
  }
}
@media (max-width: 640px) {
  .topbar-in {
    padding: 10px 16px;
  }
  .topright {
    width: 100%;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }
  .topnav {
    height: 44px;
  }
  .brand-sub {
    display: none;
  }
  .main-container {
    padding: 16px 16px 56px;
  }
  h1 {
    font-size: 22px;
  }
  .card {
    padding: 18px 16px;
  }
  .p-rm {
    font-size: 22px;
  }
  .ref-side-grid {
    grid-template-columns: 1fr;
  }
  .action {
    flex-direction: column;
    align-items: stretch;
  }
  .action .btn {
    width: 100%;
  }
  .drop-actions .btn {
    width: 100%;
  }
  input[type='date'] {
    width: 100%;
  }
}
</style>
