<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
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
import GhostOverlay from '@/components/GhostOverlay.vue'
import PhotoDropzone from '@/components/PhotoDropzone.vue'
import PhotoGuideCard from '@/components/PhotoGuideCard.vue'
import ReferencePanel from '@/components/ReferencePanel.vue'
import { formatDateID, formatDecimalID, getTodayISO } from '@/utils/formatters'

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

const todayISO = getTodayISO()
const visitDate = ref(todayISO)

const selectedFile = ref<File | null>(null)
const previewUrl = ref('')
const fileError = ref('')
const isConfirmed = ref(false)
const isLoadingSample = ref(false)
const isSubmitting = ref(false)
const liveAnnouncement = ref('')

// Panel foto acuan state (U1)
const activeRefTab = ref<'baseline' | 'latest'>('baseline')
const showRefContour = ref(false)

const photoDropzoneRef = ref<InstanceType<typeof PhotoDropzone> | null>(null)
const ghostOverlayRef = ref<InstanceType<typeof GhostOverlay> | null>(null)

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
    : 'Foto diambil sesuai panduan pengambilan foto.'
})

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
    fileError.value = 'Berkas harus berupa gambar JPG atau PNG.'
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
  nextTick(() => {
    ghostOverlayRef.value?.focusReplace()
  })
}

function clearPhoto() {
  revokePreview()
  selectedFile.value = null
  isConfirmed.value = false
  fileError.value = ''
  submitError.value = ''
  nextTick(() => {
    photoDropzoneRef.value?.resetAndFocus()
  })
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
      if (err.status === 403) {
        fileError.value =
          err.message || 'Foto sampel hanya tersedia untuk pasien mode demo.'
      } else if (err.status === 404) {
        fileError.value =
          err.message || 'Pasien atau berkas foto sampel demo tidak ditemukan di server.'
      } else if (err.status === 0) {
        fileError.value =
          'Tidak dapat terhubung ke server backend untuk memuat foto sampel.'
      } else {
        fileError.value = err.message
      }
    } else {
      fileError.value = 'Tidak dapat terhubung ke server backend untuk memuat foto sampel.'
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
    nextTick(() => {
      photoDropzoneRef.value?.resetAndFocus()
    })
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
              <strong>{{ formatDecimalID(pendingDraft.area_pct) }}%</strong> kanvas. Pilih untuk
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

            <!-- Panel Foto Acuan (U1) -->
            <ReferencePanel
              v-model:active-tab="activeRefTab"
              v-model:show-contour="showRefContour"
              :is-follow-up="isFollowUp"
              :has-distinct-latest="hasDistinctLatestRef"
              :active-visit="activeRefVisit"
              :active-image-url="activeRefImageUrl"
              :active-overlay-url="activeRefOverlayUrl"
              :active-display-url="activeRefDisplayUrl"
            />

            <PhotoDropzone
              ref="photoDropzoneRef"
              :has-file="Boolean(selectedFile)"
              :is-demo="Boolean(patient?.is_demo)"
              :is-loading-sample="isLoadingSample"
              :error-message="fileError"
              @select-file="handleSelectedFile"
              @load-sample="loadDemoSamplePhoto"
            />

            <GhostOverlay
              v-if="selectedFile"
              ref="ghostOverlayRef"
              :file="selectedFile"
              :preview-url="previewUrl"
              :is-follow-up="isFollowUp"
              :next-visit-number="nextVisitNumber"
              :visit-date="visitDate"
              :ref-image-url="activeRefDisplayUrl"
              :ref-label="activeRefTab === 'latest' && hasDistinctLatestRef ? 'Kunjungan Terakhir' : 'Baseline A₀'"
              :ref-visit-date="activeRefVisit?.visit_date ?? ''"
              :is-submitting="isSubmitting"
              @replace="clearPhoto"
              @announce="liveAnnouncement = $event"
            />

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

          <PhotoGuideCard />
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped src="../assets/h3_unggah.css"></style>
