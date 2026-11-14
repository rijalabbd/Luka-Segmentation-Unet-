<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  ApiError,
  checkServerHealth,
  fetchPatient,
  fetchPatientVisits,
  fetchVisit,
  resolveStorageUrl,
} from '@/api/patients'
import type { PatientSummary, VisitRecord } from '@/types/patient'
import { formatDateID, formatDecimalID } from '@/utils/formatters'

const route = useRoute()

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
const isCalibrated = computed(() => visit.value?.measure_mode === 'calibrated' && visit.value?.area_cm2 !== null)

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
  if (isBaselineVisit.value) return 'Final · Baseline'
  return 'Final — Tersimpan'
})

const statusChipClass = computed(() => {
  if (!visit.value) return 'draft'
  if (visit.value.status === 'draft') return 'draft'
  return isBaselineVisit.value ? 'base' : 'final'
})

const bannerInfo = computed(() => {
  if (!visit.value) {
    return { cls: 'draft', title: '', text: '' }
  }
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

const baselineFinalVisit = computed<VisitRecord | null>(() => finalVisits.value[0] ?? null)

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
    if (err instanceof ApiError) {
      loadError.value = err.message
    } else {
      loadError.value = 'Gagal memuat detail kunjungan.'
    }
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadPageData()
})

watch(
  () => route.params.visitId,
  () => {
    loadPageData()
  },
)
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
          :to="visit ? `/pemeriksaan/${encodeURIComponent(visit.patient_id)}/unggah` : '/pemeriksaan'"
        >
          <span aria-hidden="true">←</span>
          {{ visit ? 'Kembali ke Unggah Foto' : 'Kembali ke Pilih Pasien' }}
        </RouterLink>
        <template v-if="visit">
          <span aria-hidden="true">/</span>
          <span>{{ visit.patient_id }}</span>
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
                    <input
                      id="toggle-mask-overlay"
                      v-model="showMaskOverlay"
                      type="checkbox"
                    />
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
                    <small>{{
                      showMaskOverlay ? 'Foto dengan overlay masker' : 'Overlay disembunyikan'
                    }}</small>
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
              <p id="areaLimit" class="m-limit">
                {{
                  isCalibrated
                    ? 'Luas dihitung dari kalibrasi penggaris dua titik pada bidang penggaris. Tidak mengoreksi perbedaan sudut pandang.'
                    : 'Estimasi relatif terhadap luas citra (% kanvas), tanpa penanda kalibrasi fisik. Bukan ukuran dalam cm².'
                }}
              </p>
              <p v-if="isBaselineVisit" class="m-sub" style="margin-top: 10px">
                Baseline acuan A₀:
                {{
                  baselineFinalVisit
                    ? formatDecimalID(baselineFinalVisit.area_pct)
                    : formatDecimalID(visit.area_pct)
                }}%
              </p>
            </section>
          </div>
        </div>

        <section v-if="isDraft" id="narrWait" class="panel narr-wait">
          <b>Narasi dibuat setelah hasil dikonfirmasi.</b> Catatan klinis dan ringkasan pasien
          disusun setelah hasil dikonfirmasi dan disimpan.
        </section>

        <section v-else class="panel final-basic-narr">
          <h2>Status Kunjungan Final</h2>
          <p v-if="visit.trend_status">
            Status tren tersimpan: <b>{{ visit.trend_status }}</b>
            <template v-if="visit.pac !== null"> · PAC {{ visit.pac }}%</template>
          </p>
          <p v-else>Kunjungan baseline tersimpan tanpa perhitungan PAC.</p>
          <p v-if="visit.patient_narrative">
            <b>Ringkasan Pasien:</b> {{ visit.patient_narrative }}
          </p>
          <p v-if="visit.clinician_notes">
            <b>Catatan Klinisi:</b> {{ visit.clinician_notes }}
          </p>
        </section>

        <div v-if="isDraft" id="actions" class="actions sticky">
          <p class="hint">
            Periksa batas masker segmentasi pada foto. Jika sesuai, setujui dan simpan. Jika memilih
            Foto Ulang, draf beserta kalibrasi pada kunjungan ini akan dibuang.
          </p>
          <div class="btn-row">
            <button id="bDiscard" class="btn btn-secondary" type="button">Foto Ulang</button>
            <button id="bSave" class="btn btn-primary" type="button">Setujui dan Simpan</button>
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
  </div>
</template>

<style scoped src="../assets/h4_hasil.css"></style>
