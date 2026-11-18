<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import {
  checkServerHealth,
  createDraftVisit,
  deleteVisit,
  fetchDemoSamplePhoto,
  fetchPatient,
  fetchPatientVisits,
  resolveStorageUrl,
} from '@/api/patients';
import GhostOverlay from '@/components/GhostOverlay.vue';
import PhotoDropzone from '@/components/PhotoDropzone.vue';
import PhotoGuideCard from '@/components/PhotoGuideCard.vue';
import ReferencePanel from '@/components/ReferencePanel.vue';
import type { PatientSummary, VisitRecord } from '@/types/patient';
import {
  STAGE1_OPACITY_STORAGE_KEY,
  useGhostOpacity,
} from '@/composables/useGhostOpacity';
import {
  GHOST_DEFAULT_OPACITY,
  GHOST_DEFAULT_SCALE,
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  isGhostModified,
} from '@/utils/ghostTransform';
import { buildReferenceComparisonInfo } from '@/utils/referenceMessage';

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'];

function getTodayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatDateParts(dateStr: string | null | undefined): { day: number; month: string; year: number } | null {
  if (!dateStr) return null;
  const parts = dateStr.slice(0, 10).split('-').map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return null;
  const [year, monthIdx, day] = parts;
  const month = MONTHS_SHORT[monthIdx - 1];
  if (!month) return null;
  return { day, month, year };
}

function formatDateShort(dateStr: string | null | undefined): string {
  const p = formatDateParts(dateStr);
  if (!p) return dateStr || '-';
  return `${p.day} ${p.month} ${p.year}`;
}

function formatDateDayMonth(dateStr: string | null | undefined): string {
  const p = formatDateParts(dateStr);
  if (!p) return dateStr || '-';
  return `${p.day} ${p.month}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`;
}

const route = useRoute();
const router = useRouter();
const patientId = computed(() => String(route.params.patientId || ''));

const serverOnline = ref<boolean | null>(null);
const isLoading = ref(true);
const pageError = ref('');

const patient = ref<PatientSummary | null>(null);
const finalVisits = ref<VisitRecord[]>([]);
const pendingDraft = ref<VisitRecord | null>(null);

const todayIso = getTodayIso();
const visitDate = ref(todayIso);
const isEditingDate = ref(false);

const activeRefTab = ref<'baseline' | 'latest'>('baseline');
const showRefContour = ref(false);

const selectedFile = ref<File | null>(null);
const previewUrl = ref('');
const fileError = ref('');

const ghostActive = ref(false);
const { opacity: ghostOpacity } = useGhostOpacity(STAGE1_OPACITY_STORAGE_KEY, GHOST_DEFAULT_OPACITY);
const ghostScale = ref(GHOST_DEFAULT_SCALE);
const ghostX = ref(0);
const ghostY = ref(0);

const canResetGhost = computed(() =>
  isGhostModified(ghostScale.value, ghostX.value, ghostY.value, ghostOpacity.value),
);

function resetGhostPositionAndScale() {
  ghostScale.value = GHOST_DEFAULT_SCALE;
  ghostX.value = 0;
  ghostY.value = 0;
}

function resetGhostAll() {
  ghostOpacity.value = GHOST_DEFAULT_OPACITY;
  resetGhostPositionAndScale();
}

const distanceConfirmed = ref(false);
const isSubmitting = ref(false);
const isDiscardingDraft = ref(false);
const submitError = ref('');
const liveAnnouncement = ref('');

const isFollowUp = computed(() => finalVisits.value.length > 0);
const nextVisitIndex = computed(() => finalVisits.value.length + 1);
const visitBadgeText = computed(() =>
  isFollowUp.value ? `Kunjungan ke-${nextVisitIndex.value}` : 'Kunjungan pertama',
);

const refComparison = computed(() =>
  buildReferenceComparisonInfo(finalVisits.value, activeRefTab.value, formatDateShort),
);

const latestVisit = computed<VisitRecord | null>(() => {
  if (finalVisits.value.length === 0) return null;
  return finalVisits.value[finalVisits.value.length - 1];
});

const hasDistinctLatestRef = computed(() => refComparison.value.hasDistinctLatestWithPhoto);

const activeRefVisit = computed<VisitRecord | null>(() => refComparison.value.effectiveRefVisit);

const activeRefImageUrl = computed(() => resolveStorageUrl(activeRefVisit.value?.image_path) || null);
const activeRefOverlayUrl = computed(() => resolveStorageUrl(activeRefVisit.value?.overlay_path) || null);
const activeRefDateLabel = computed(() => formatDateShort(activeRefVisit.value?.visit_date));
const latestShortDate = computed(() =>
  formatDateDayMonth(refComparison.value.latestWithPhotoVisit?.visit_date),
);

const latestFinalDate = computed(() => latestVisit.value?.visit_date?.slice(0, 10) || '');
const minDate = computed(() => latestFinalDate.value || '2020-01-01');
const maxDate = todayIso;

const visitDateDisplay = computed(() => {
  const formatted = formatDateShort(visitDate.value);
  return visitDate.value === todayIso ? `Hari ini, ${formatted}` : formatted;
});

const dateError = computed(() => {
  if (!visitDate.value) return 'Tanggal kunjungan wajib diisi.';
  if (visitDate.value > maxDate) return 'Tanggal kunjungan tidak boleh melebihi hari ini.';
  if (latestFinalDate.value && visitDate.value < latestFinalDate.value) {
    return 'Tanggal kunjungan tidak boleh lebih awal dari kunjungan sebelumnya.';
  }
  return '';
});

const canRunDetection = computed(
  () => Boolean(selectedFile.value) && !dateError.value && distanceConfirmed.value && !isSubmitting.value,
);

const statusReasonText = computed(() => {
  if (isSubmitting.value) return 'Sedang menganalisis. Jangan tutup halaman ini.';
  if (!selectedFile.value) return 'Unggah foto luka terlebih dahulu.';
  if (dateError.value) return dateError.value;
  if (!distanceConfirmed.value) return 'Centang konfirmasi di atas.';
  return 'Siap dianalisis.';
});

const confirmLabel = computed(() => {
  if (!isFollowUp.value || !activeRefImageUrl.value) return 'Foto sudah sesuai panduan.';
  if (activeRefTab.value === 'latest' && hasDistinctLatestRef.value) {
    return 'Jarak dan sudut foto sudah sama dengan foto terakhir.';
  }
  return 'Jarak dan sudut foto sudah sama dengan foto awal.';
});

const serverLabel = computed(() => {
  if (serverOnline.value === true) return 'Server terhubung';
  if (serverOnline.value === false) return 'Server tidak terhubung';
  return 'Memeriksa server...';
});

function revokePreviewUrl() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = '';
  }
}

function handleSelectedFile(file: File) {
  const lowerName = file.name.toLowerCase();
  const isAllowedType =
    file.type === 'image/jpeg' ||
    file.type === 'image/png' ||
    lowerName.endsWith('.jpg') ||
    lowerName.endsWith('.jpeg') ||
    lowerName.endsWith('.png');

  if (!isAllowedType) {
    fileError.value = 'Berkas harus berupa gambar JPG atau PNG.';
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    fileError.value = 'Ukuran foto maksimal 10 MB.';
    return;
  }

  revokePreviewUrl();
  selectedFile.value = file;
  previewUrl.value = URL.createObjectURL(file);
  fileError.value = '';
  submitError.value = '';
  liveAnnouncement.value = `Foto ${file.name} siap dianalisis.`;
}

function clearPhoto() {
  revokePreviewUrl();
  selectedFile.value = null;
  fileError.value = '';
  ghostActive.value = false;
  resetGhostPositionAndScale();
  distanceConfirmed.value = false;
  submitError.value = '';
}

async function loadDemoSamplePhoto() {
  if (!patient.value) return;
  fileError.value = '';
  try {
    const file = await fetchDemoSamplePhoto(patient.value.id);
    handleSelectedFile(file);
  } catch (err) {
    fileError.value = err instanceof Error ? err.message : 'Gagal memuat foto sampel demo.';
  }
}

async function handleDiscardDraft() {
  if (!pendingDraft.value || isDiscardingDraft.value) return;
  isDiscardingDraft.value = true;
  submitError.value = '';
  try {
    await deleteVisit(pendingDraft.value.id);
    pendingDraft.value = null;
    liveAnnouncement.value = 'Pemeriksaan yang belum disimpan telah dibuang.';
  } catch (err) {
    submitError.value = err instanceof Error ? err.message : 'Gagal membuang draf pemeriksaan.';
  } finally {
    isDiscardingDraft.value = false;
  }
}

async function handleRunDetection() {
  if (!patient.value || !selectedFile.value || dateError.value || !distanceConfirmed.value || isSubmitting.value) {
    return;
  }
  isSubmitting.value = true;
  submitError.value = '';
  liveAnnouncement.value = 'Sedang menganalisis foto luka.';
  try {
    const created = await createDraftVisit(
      patient.value.id,
      visitDate.value,
      selectedFile.value,
      distanceConfirmed.value,
    );
    await router.push({ name: 'hasil-kunjungan', params: { visitId: created.id } });
  } catch (err) {
    submitError.value = err instanceof Error ? err.message : 'Gagal menganalisis foto luka.';
    liveAnnouncement.value = 'Analisis foto gagal.';
  } finally {
    isSubmitting.value = false;
  }
}

async function loadPageData() {
  isLoading.value = true;
  pageError.value = '';
  clearPhoto();
  activeRefTab.value = 'baseline';
  showRefContour.value = false;
  isEditingDate.value = false;
  visitDate.value = getTodayIso();

  try {
    try {
      await checkServerHealth();
      serverOnline.value = true;
    } catch {
      serverOnline.value = false;
    }

    const [patientData, allVisits] = await Promise.all([
      fetchPatient(patientId.value),
      fetchPatientVisits(patientId.value, 'all'),
    ]);

    patient.value = patientData;
    const sortedFinals = allVisits
      .filter((v) => v.status === 'final')
      .sort((a, b) => (a.visit_index ?? a.id) - (b.visit_index ?? b.id));
    finalVisits.value = sortedFinals;

    const drafts = allVisits
      .filter((v) => v.status === 'draft')
      .sort((a, b) => b.id - a.id);
    pendingDraft.value = drafts[0] ?? null;
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : 'Gagal memuat data pasien.';
  } finally {
    isLoading.value = false;
  }
}

watch(activeRefTab, () => {
  resetGhostPositionAndScale();
});

watch(patientId, () => {
  void loadPageData();
});

onMounted(() => {
  void loadPageData();
});

onBeforeUnmount(() => {
  revokePreviewUrl();
});
</script>

<template>
  <div class="h3-page">
    <a class="skip-link" href="#main-content">Lewati ke konten utama</a>

    <header class="topbar">
      <div class="topbar-in">
        <RouterLink class="brand" :to="{ name: 'beranda' }">
          <span class="brand-mark" aria-hidden="true">+</span>
          <span>
            <span class="brand-name">WoundAI</span>
            <span class="brand-sub">Pemantauan Ulkus Kusta</span>
          </span>
        </RouterLink>

        <div class="topright">
          <nav class="topnav" aria-label="Navigasi utama">
            <RouterLink :to="{ name: 'beranda' }">Beranda</RouterLink>
            <RouterLink :to="{ name: 'pilih-pasien' }" aria-current="page">Pemeriksaan</RouterLink>
          </nav>

          <span
            class="server-pill"
            :class="{ online: serverOnline === true, offline: serverOnline === false }"
            role="status"
          >
            <span class="dot" aria-hidden="true"></span>
            <span class="server-text">{{ serverLabel }}</span>
          </span>
        </div>
      </div>
    </header>

    <main id="main-content" class="main-container">
      <RouterLink id="back-link" class="back" :to="{ name: 'pilih-pasien' }">
        ← Ganti pasien
      </RouterLink>

      <div class="title-row">
        <h1>Foto Luka</h1>
        <span v-if="!isLoading && patient" id="badge" class="badge">{{ visitBadgeText }}</span>
      </div>

      <div v-if="isLoading" class="card loading-card">
        <p class="muted">Memuat data pasien...</p>
      </div>

      <div v-else-if="pageError" class="error-banner" role="alert">
        <div>
          <strong>Data pasien tidak dapat dimuat</strong>
          <p>{{ pageError }}</p>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" @click="loadPageData">Muat Ulang</button>
      </div>

      <template v-else-if="patient">
        <section class="patient" aria-label="Identitas pasien">
          <div class="p-line">
            <span class="p-rm">{{ patient.id }}</span>
            <span class="p-name">{{ patient.nama || 'Tanpa nama' }}</span>
            <span class="p-attrs">
              <span v-if="patient.umur !== null">{{ patient.umur }} th</span>
              <span v-if="patient.jk">{{ patient.jk }}</span>
              <span v-if="patient.lokasi">{{ patient.lokasi }}</span>
            </span>
          </div>
          <RouterLink
            id="link-patient-history"
            class="btn btn-secondary btn-sm"
            :to="{ name: 'riwayat-pasien', params: { patientId: patient.id } }"
          >
            Riwayat
          </RouterLink>
        </section>

        <section
          v-if="pendingDraft"
          id="draft-warning"
          class="draft-banner"
          role="region"
          aria-label="Pemeriksaan belum disimpan"
        >
          <div class="draft-banner-text">
            <strong>Pemeriksaan {{ formatDateShort(pendingDraft.visit_date) }} belum disimpan</strong>
            <p>
              Foto sudah dianalisis tapi belum dikonfirmasi. Lanjutkan untuk meninjau hasilnya, atau
              buang untuk mulai dari foto baru.
            </p>
          </div>
          <div class="draft-banner-actions">
            <button
              id="btn-resume-draft"
              type="button"
              class="btn btn-primary"
              @click="router.push({ name: 'hasil-kunjungan', params: { visitId: pendingDraft.id } })"
            >
              Lanjutkan
            </button>
            <button
              id="btn-discard-draft"
              type="button"
              class="btn btn-secondary"
              :disabled="isDiscardingDraft"
              @click="handleDiscardDraft"
            >
              {{ isDiscardingDraft ? 'Membuang...' : 'Buang dan mulai baru' }}
            </button>
          </div>
        </section>

        <template v-else>
          <section class="card" aria-label="Formulir unggah foto luka">
            <div class="date-row">
              <div class="date-summary">
                <span class="date-label">Tanggal:</span>
                <strong>{{ visitDateDisplay }}</strong>
                <button
                  type="button"
                  class="btn-text"
                  @click="isEditingDate = !isEditingDate"
                >
                  {{ isEditingDate || dateError ? 'Tutup' : 'Ubah' }}
                </button>
              </div>
              <div v-if="isEditingDate || dateError" class="date-input-wrap">
                <label class="sr-only" for="tgl">Tanggal pemeriksaan</label>
                <input
                  id="tgl"
                  v-model="visitDate"
                  type="date"
                  :min="minDate"
                  :max="maxDate"
                />
              </div>
              <p v-if="dateError" id="tgl-err" class="error" role="alert">{{ dateError }}</p>
            </div>

            <p v-if="!isFollowUp" class="baseline-note">
              Foto ini menjadi foto awal untuk kunjungan berikutnya.
            </p>

            <div v-if="isFollowUp" class="columns">
              <div class="col">
                <ReferencePanel
                  v-model:active-ref-tab="activeRefTab"
                  v-model:show-contour="showRefContour"
                  :has-distinct-latest="hasDistinctLatestRef"
                  :active-date-label="activeRefDateLabel"
                  :latest-short-date="latestShortDate"
                  :active-image-url="activeRefImageUrl"
                  :active-overlay-url="activeRefOverlayUrl"
                  :comparison-sentence="refComparison.comparisonSentence"
                  :missing-photo-sentence="refComparison.missingPhotoSentence"
                />
              </div>
              <div class="col">
                <PhotoDropzone
                  v-if="!selectedFile"
                  :error="fileError"
                  :show-sample-button="patient.is_demo"
                  :ref-image-url="activeRefImageUrl"
                  :ref-label="activeRefTab === 'latest' && hasDistinctLatestRef ? 'terakhir' : 'awal'"
                  :is-follow-up="isFollowUp"
                  @select="handleSelectedFile"
                  @sample="loadDemoSamplePhoto"
                />
                <GhostOverlay
                  v-else
                  v-model:ghost-x="ghostX"
                  v-model:ghost-y="ghostY"
                  v-model:ghost-scale="ghostScale"
                  :preview-url="previewUrl"
                  :file-name="selectedFile.name"
                  :file-size-text="formatFileSize(selectedFile.size)"
                  :ref-image-url="activeRefImageUrl"
                  :ghost-active="ghostActive"
                  :ghost-opacity="ghostOpacity"
                  :disabled="isSubmitting"
                  @replace="clearPhoto"
                />
              </div>
            </div>

            <div v-else class="single-col">
              <PhotoDropzone
                v-if="!selectedFile"
                :error="fileError"
                :show-sample-button="patient.is_demo"
                :ref-image-url="null"
                :is-follow-up="false"
                @select="handleSelectedFile"
                @sample="loadDemoSamplePhoto"
              />
              <GhostOverlay
                v-else
                v-model:ghost-x="ghostX"
                v-model:ghost-y="ghostY"
                v-model:ghost-scale="ghostScale"
                :preview-url="previewUrl"
                :file-name="selectedFile.name"
                :file-size-text="formatFileSize(selectedFile.size)"
                :ref-image-url="null"
                :ghost-active="false"
                :ghost-opacity="ghostOpacity"
                :disabled="isSubmitting"
                @replace="clearPhoto"
              />
            </div>

            <div v-if="selectedFile && isFollowUp && activeRefImageUrl" id="ghostCtl" class="ghost-ctl">
              <div class="ghost-row">
                <button
                  id="gsw"
                  type="button"
                  role="switch"
                  :aria-checked="ghostActive"
                  class="swbtn"
                  @click="ghostActive = !ghostActive"
                >
                  <span class="track" aria-hidden="true"></span>
                  <span>Tumpuk foto awal</span>
                </button>

                <template v-if="ghostActive">
                  <label class="op" for="gop">
                    <span>Transparansi</span>
                    <input
                      id="gop"
                      v-model.number="ghostOpacity"
                      type="range"
                      min="0"
                      max="80"
                      step="5"
                    />
                    <output id="gout">{{ ghostOpacity }}%</output>
                  </label>

                  <label class="op" for="gscale">
                    <span>Ukuran</span>
                    <input
                      id="gscale"
                      v-model.number="ghostScale"
                      type="range"
                      :min="GHOST_SCALE_MIN"
                      :max="GHOST_SCALE_MAX"
                      step="1"
                    />
                    <output id="gscale-out">{{ ghostScale }}%</output>
                  </label>

                  <button
                    id="greset"
                    type="button"
                    class="btn btn-secondary btn-xs"
                    :disabled="!canResetGhost"
                    @click="resetGhostAll"
                  >
                    Atur ulang
                  </button>
                </template>
              </div>

              <p id="ghost-note" class="ghost-note">
                Seret foto awal untuk menggeser. Samakan lebar pergelangan atau sisi kaki, bukan tepi luka. Foto yang dianalisis tetap asli.
              </p>
            </div>

            <div v-if="submitError" id="submit-error-banner" class="error-banner" role="alert">
              <div>
                <strong>Foto belum bisa dianalisis</strong>
                <p>{{ submitError }}</p>
              </div>
              <button
                id="btn-retry-submit"
                type="button"
                class="btn btn-secondary btn-sm"
                :disabled="isSubmitting"
                @click="handleRunDetection"
              >
                Coba Lagi
              </button>
            </div>

            <div class="sticky-action-bar">
              <div id="confirm" class="confirm">
                <input
                  id="chk"
                  v-model="distanceConfirmed"
                  type="checkbox"
                  :disabled="isSubmitting"
                />
                <label id="chk-lbl" for="chk">{{ confirmLabel }}</label>
              </div>

              <div class="action">
                <p
                  id="reason"
                  class="reason"
                  :class="{ 'sr-only': canRunDetection }"
                  aria-live="polite"
                >
                  {{ statusReasonText }}
                </p>
                <button
                  id="run"
                  type="button"
                  class="btn btn-primary"
                  :disabled="!canRunDetection || isSubmitting"
                  @click="handleRunDetection"
                >
                  <span v-if="isSubmitting" class="spinner" aria-hidden="true"></span>
                  <span id="run-txt">{{ isSubmitting ? 'Menganalisis foto...' : 'Analisis Foto' }}</span>
                </button>
              </div>
            </div>
          </section>

          <PhotoGuideCard :open-by-default="!isFollowUp || !activeRefImageUrl" />
        </template>
      </template>

      <div id="live" class="sr-only" aria-live="polite">{{ liveAnnouncement }}</div>
    </main>
  </div>
</template>

<style src="@/assets/h3_unggah.css"></style>
