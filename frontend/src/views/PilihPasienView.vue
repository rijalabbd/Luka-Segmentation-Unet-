<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { ApiError, checkServerHealth, createPatient, fetchPatients } from '@/api/patients'
import type { PatientSummary, PatientTrendBadge } from '@/types/patient'

const router = useRouter()

const activeTab = ref<'lama' | 'baru'>('lama')
const tabLamaBtn = ref<HTMLButtonElement | null>(null)
const tabBaruBtn = ref<HTMLButtonElement | null>(null)
const panelAnimKey = ref(0)

const patients = ref<PatientSummary[]>([])
const isLoading = ref(true)
const loadError = ref('')
const formServerError = ref('')
const searchQuery = ref('')
const searchInput = ref<HTMLInputElement | null>(null)
const isSubmitting = ref(false)

// Server health state sourced from GET /api/v1/health
const serverOnline = ref<boolean | null>(null)
const healthLabel = ref('Memeriksa Koneksi Server...')
const healthShortLabel = ref('Memeriksa...')

// Form state
const rm = ref('')
const nama = ref('')
const usia = ref<string>('')
const jk = ref('')
const lokasi = ref('')
const consent = ref(false)

// Validation error messages
const rmErr = ref('')
const usiaErr = ref('')
const consentErr = ref('')

// Form element refs for focus management
const rmInput = ref<HTMLInputElement | null>(null)
const usiaInput = ref<HTMLInputElement | null>(null)
const consentInput = ref<HTMLInputElement | null>(null)

const LOKASI_OPTIONS = [
  'Telapak kaki kanan',
  'Telapak kaki kiri',
  'Punggung kaki kanan',
  'Punggung kaki kiri',
  'Tungkai bawah kanan',
  'Tungkai bawah kiri',
]

function norm(s: string | null | undefined): string {
  if (!s) return ''
  return s.toLowerCase().replace(/\./g, '').replace(/\s+/g, ' ').trim()
}

const filteredPatients = computed(() => {
  const term = norm(searchQuery.value)
  if (!term) return patients.value
  return patients.value.filter((p) =>
    [p.id, p.nama, p.lokasi].some((val) => norm(val).includes(term)),
  )
})

const countText = computed(() => {
  if (isLoading.value) return 'Memuat daftar pasien...'
  if (loadError.value) return 'Daftar pasien belum dapat dimuat'
  const term = norm(searchQuery.value)
  if (term) {
    const n = filteredPatients.value.length
    const base = `${n} dari ${patients.value.length} pasien`
    return n === 1 ? `${base} · tekan Enter untuk memilih` : base
  }
  return `${patients.value.length} pasien terdaftar`
})

function badgeClass(status: PatientTrendBadge): string {
  if (status === 'menurun') return 'good'
  if (status === 'meningkat') return 'warn'
  if (status === 'stabil') return 'neutral'
  return 'new'
}

function badgeText(p: PatientSummary): string {
  if (p.status === 'menurun') return 'Tren Menurun'
  if (p.status === 'meningkat') return 'Tren Meningkat'
  if (p.status === 'stabil') return 'Tren Stabil'
  if (p.status === 'tidak_dapat_dihitung') return 'PAC tidak dapat dihitung'
  if (p.status === 'baseline') return 'Kunjungan awal (baseline)'
  return 'Belum ada kunjungan'
}

function patientAttrs(p: PatientSummary): string[] {
  const items: string[] = []
  if (p.umur !== null && p.umur !== undefined) items.push(`${p.umur} tahun`)
  if (p.jk) items.push(p.jk)
  if (p.lokasi) items.push(p.lokasi)
  return items
}

function patientUploadUrl(id: string): string {
  return `/pemeriksaan/${encodeURIComponent(id)}/unggah`
}

function patientHistoryUrl(id: string): string {
  return `/pasien/${encodeURIComponent(id)}`
}

const RM_PATTERN = /^[A-Za-z0-9][A-Za-z0-9\-_]{2,19}$/

// Empty state shortcut: carry an RM-shaped search term into the new-patient form.
async function goToRegister() {
  const term = searchQuery.value.trim()
  if (RM_PATTERN.test(term) && !rm.value) rm.value = term.toUpperCase()
  await selectTab('baru')
  await nextTick()
  rmInput.value?.focus()
}

function handleCardSpaceKey(e: KeyboardEvent, id: string) {
  if (e.key === ' ') {
    e.preventDefault()
    router.push(patientUploadUrl(id))
  }
}

function clearSearch() {
  searchQuery.value = ''
  searchInput.value?.focus()
}

function handleSearchKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && searchQuery.value) {
    searchQuery.value = ''
  } else if (e.key === 'Enter' && searchQuery.value.trim() && filteredPatients.value.length === 1) {
    e.preventDefault()
    router.push(patientUploadUrl(filteredPatients.value[0].id))
  }
}

async function selectTab(tab: 'lama' | 'baru', focusBtn = false) {
  activeTab.value = tab
  panelAnimKey.value++
  await nextTick()
  updateIndicator()
  if (focusBtn) {
    if (tab === 'lama') tabLamaBtn.value?.focus()
    else tabBaruBtn.value?.focus()
  }
}

// Sliding tab underline: follows the active tab instead of jumping.
const indicatorStyle = ref<Record<string, string>>({ opacity: '0' })

function updateIndicator() {
  const btn = activeTab.value === 'lama' ? tabLamaBtn.value : tabBaruBtn.value
  if (!btn) return
  indicatorStyle.value = {
    opacity: '1',
    width: `${btn.offsetWidth}px`,
    transform: `translateX(${btn.offsetLeft}px)`,
  }
}

function handleTabKeydown(e: KeyboardEvent, current: 'lama' | 'baru') {
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    const next = current === 'lama' ? 'baru' : 'lama'
    selectTab(next, true)
  } else if (e.key === 'Home') {
    e.preventDefault()
    selectTab('lama', true)
  } else if (e.key === 'End') {
    e.preventDefault()
    selectTab('baru', true)
  }
}

function validRM(): boolean {
  const v = rm.value.trim()
  if (!v) {
    rmErr.value = 'Nomor rekam medis wajib diisi.'
    return false
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9\-_]{2,19}$/.test(v)) {
    rmErr.value = 'Gunakan huruf, angka, tanda hubung, atau garis bawah (3 sampai 20 karakter), contoh: RM-0031.'
    return false
  }
  if (patients.value.some((p) => p.id.toLowerCase() === v.toLowerCase())) {
    rmErr.value = 'Nomor RM ini sudah terdaftar. Pilih dari tab Pasien Lama.'
    return false
  }
  rmErr.value = ''
  return true
}

function validUsia(): boolean {
  const raw = String(usia.value ?? '').trim()
  if (raw === '') {
    usiaErr.value = ''
    return true
  }
  const n = Number(raw)
  if (!Number.isInteger(n) || n < 0 || n > 120) {
    usiaErr.value = 'Masukkan usia antara 0 dan 120 tahun.'
    return false
  }
  usiaErr.value = ''
  return true
}

function validConsent(): boolean {
  if (!consent.value) {
    consentErr.value =
      'Centang persetujuan terlebih dahulu. Dokumentasi foto luka tidak boleh dilanjutkan tanpa informed consent.'
    return false
  }
  consentErr.value = ''
  return true
}

function onRmInput() {
  if (rmErr.value) validRM()
}

function onConsentChange() {
  if (consent.value || consentErr.value) validConsent()
}

async function loadData() {
  isLoading.value = true
  loadError.value = ''
  try {
    const health = await checkServerHealth()
    serverOnline.value = health.status === 'ok'
    healthLabel.value = health.label
    healthShortLabel.value = health.short_label
  } catch {
    serverOnline.value = false
    healthLabel.value = 'Server Lokal Terputus · Periksa Backend'
    healthShortLabel.value = 'Offline'
  }

  try {
    patients.value = await fetchPatients()
  } catch (err) {
    patients.value = []
    loadError.value =
      err instanceof Error
        ? err.message
        : 'Gagal terhubung ke server backend. Data pasien tidak dapat ditampilkan.'
  } finally {
    isLoading.value = false
  }
}

async function handleSubmit() {
  formServerError.value = ''
  const a = validRM()
  const b = validUsia()
  const c = validConsent()

  if (!a) {
    rmInput.value?.focus()
    return
  }
  if (!b) {
    usiaInput.value?.focus()
    return
  }
  if (!c) {
    consentInput.value?.focus()
    return
  }

  const normalizedId = rm.value.trim().toUpperCase()
  const parsedAge = String(usia.value ?? '').trim() === '' ? null : Number(usia.value)

  isSubmitting.value = true
  try {
    const created = await createPatient({
      id: normalizedId,
      nama: nama.value.trim() || null,
      umur: parsedAge,
      jk: jk.value || null,
      lokasi: lokasi.value.trim() || null,
      consent: consent.value,
    })
    patients.value.push(created)
    await router.push(patientUploadUrl(created.id))
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      rmErr.value = err.message
      rmInput.value?.focus()
      return
    }
    if (err instanceof ApiError && err.status === 422) {
      rmErr.value = err.message
      rmInput.value?.focus()
      return
    }
    formServerError.value =
      err instanceof Error
        ? err.message
        : 'Gagal menyimpan data pasien karena server lokal tidak terjangkau.'
  } finally {
    isSubmitting.value = false
  }
}

onMounted(async () => {
  document.title = 'Pilih Pasien · Dokumentasi Luka'
  window.addEventListener('resize', updateIndicator)
  updateIndicator()
  await loadData()
  // Desktop only: the clinician can start typing immediately. Skipped on touch to avoid popping the keyboard.
  if (!loadError.value && window.matchMedia('(pointer: fine)').matches) {
    await nextTick()
    searchInput.value?.focus()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateIndicator)
})
</script>

<template>
  <div class="h2-page">
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

        <div
          class="secure"
          :class="{ offline: serverOnline === false, pending: serverOnline === null }"
          role="status"
          :aria-label="healthLabel"
        >
          <span class="dot" aria-hidden="true"></span>
          <svg
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="7" width="10" height="7" rx="1.5" />
            <path d="M5 7V5a3 3 0 0 1 6 0v2" />
          </svg>
          <span class="full" aria-hidden="true">{{ healthLabel }}</span>
          <span class="short" aria-hidden="true">{{ healthShortLabel }}</span>
        </div>

        <nav class="topnav" aria-label="Navigasi utama">
          <RouterLink to="/">Beranda</RouterLink>
          <RouterLink to="/pemeriksaan" aria-current="page">Pemeriksaan</RouterLink>
        </nav>
      </div>
    </header>

    <main id="main-content" class="main-container">
      <div class="page-head">
        <h1>Pilih Pasien</h1>
        <p>
          Pilih pasien yang sudah terdaftar atau daftarkan pasien baru untuk memulai pemeriksaan.
        </p>
      </div>

      <!-- Error Banner when Backend is Unreachable (No Offline Demo Fallback) -->
      <div v-if="loadError" class="error-banner" role="alert">
        <div class="error-banner-body">
          <strong>Koneksi Server Lokal Gagal</strong>
          <p>{{ loadError }}</p>
        </div>
        <button class="btn btn-retry" type="button" @click="loadData">Muat Ulang</button>
      </div>

      <div class="tabs" role="tablist" aria-label="Jenis pasien">
        <button
          id="tab-lama"
          ref="tabLamaBtn"
          class="tab"
          role="tab"
          type="button"
          aria-controls="panel-lama"
          :aria-selected="activeTab === 'lama'"
          :tabindex="activeTab === 'lama' ? 0 : -1"
          @click="selectTab('lama')"
          @keydown="handleTabKeydown($event, 'lama')"
        >
          Pasien Lama
        </button>
        <button
          id="tab-baru"
          ref="tabBaruBtn"
          class="tab"
          role="tab"
          type="button"
          aria-controls="panel-baru"
          :aria-selected="activeTab === 'baru'"
          :tabindex="activeTab === 'baru' ? 0 : -1"
          @click="selectTab('baru')"
          @keydown="handleTabKeydown($event, 'baru')"
        >
          Pasien Baru
        </button>
        <span class="tab-indicator" :style="indicatorStyle" aria-hidden="true"></span>
      </div>

      <!-- TAB 1: PASIEN LAMA -->
      <section
        id="panel-lama"
        :key="`lama-${panelAnimKey}`"
        class="panel enter"
        role="tabpanel"
        aria-labelledby="tab-lama"
        :hidden="activeTab !== 'lama'"
      >
        <div class="search">
          <label class="sr" for="q">Cari pasien</label>
          <svg
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <circle cx="9" cy="9" r="6" />
            <path d="m14 14 4 4" />
          </svg>
          <input
            id="q"
            ref="searchInput"
            v-model="searchQuery"
            type="search"
            placeholder="Cari kode RM, inisial nama, atau lokasi ulkus..."
            autocomplete="off"
            :disabled="Boolean(loadError)"
            @keydown="handleSearchKeydown"
          />
          <button
            id="clear"
            class="clear"
            :class="{ show: searchQuery.length > 0 }"
            type="button"
            aria-label="Hapus pencarian"
            @click="clearSearch"
          >
            <svg
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              aria-hidden="true"
            >
              <path d="m4 4 8 8M12 4l-8 8" />
            </svg>
          </button>
        </div>

        <p id="count" class="count" role="status" aria-live="polite">{{ countText }}</p>

        <!-- Skeleton Placeholder Cards during Initial Load (Prevents Layout Shift) -->
        <ul v-if="isLoading" class="list" aria-hidden="true">
          <li v-for="n in 3" :key="`skel-${n}`" class="card skeleton-card">
            <span class="skel-pill skel-badge"></span>
            <div class="card-main">
              <div class="rm-line">
                <span class="skel-line skel-rm"></span>
                <span class="skel-line skel-name"></span>
              </div>
              <div class="skel-line skel-attrs"></div>
              <div class="skel-line skel-history"></div>
            </div>
            <span class="skel-btn"></span>
          </li>
        </ul>

        <!-- Loaded Patient List -->
        <ul v-else-if="!loadError" id="list" class="list">
          <li
            v-for="(p, idx) in filteredPatients"
            :key="p.id"
            class="card"
            :style="{ '--i': Math.min(idx, 6) }"
          >
            <span class="badge" :class="badgeClass(p.status)" :title="p.trend_status">
              <!-- Neutral direction arrows: describe the measured change, never judge it. -->
              <svg
                v-if="p.status === 'menurun'"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M8 3v10M4 9l4 4 4-4" />
              </svg>
              <svg
                v-else-if="p.status === 'meningkat'"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M8 13V3M4 7l4-4 4 4" />
              </svg>
              <svg
                v-else-if="p.status === 'stabil'"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
              <svg
                v-else
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                aria-hidden="true"
              >
                <circle cx="8" cy="8" r="3.5" />
              </svg>
              {{ badgeText(p) }}
            </span>

            <div class="card-main">
              <div class="rm-line">
                <span class="rm">{{ p.id }}</span>
                <span v-if="p.nama" class="nama">{{ p.nama }}</span>
              </div>
              <div v-if="patientAttrs(p).length > 0" class="attrs">
                <span v-for="(attr, idx) in patientAttrs(p)" :key="idx">{{ attr }}</span>
              </div>
              <div class="history">
                <strong>{{ p.n }} kunjungan</strong> · Terakhir: {{ p.terakhir }}
              </div>
            </div>

            <div class="card-actions">
              <RouterLink
                class="btn-secondary"
                :to="patientHistoryUrl(p.id)"
                :aria-label="`Lihat riwayat pasien ${p.id}`"
              >
                Riwayat
              </RouterLink>
              <RouterLink
                class="btn card-primary-btn"
                :to="patientUploadUrl(p.id)"
                :aria-label="`Pilih pasien ${p.id}${p.nama ? ', ' + p.nama : ''}, ${p.n} kunjungan, ${p.trend_status}`"
                @keydown="handleCardSpaceKey($event, p.id)"
              >
                Pilih Pasien <span class="arrow" aria-hidden="true">→</span>
              </RouterLink>
            </div>
          </li>
        </ul>

        <div
          id="empty"
          class="empty"
          :hidden="isLoading || Boolean(loadError) || filteredPatients.length > 0"
        >
          <p v-if="searchQuery.trim()">
            Tidak ada pasien yang cocok dengan <strong>{{ searchQuery.trim() }}</strong>.
          </p>
          <p v-else>Belum ada pasien terdaftar.</p>
          <button class="btn-secondary" type="button" @click="goToRegister">
            Daftarkan sebagai pasien baru
          </button>
        </div>
      </section>

      <!-- TAB 2: PASIEN BARU -->
      <section
        id="panel-baru"
        :key="`baru-${panelAnimKey}`"
        class="panel enter"
        role="tabpanel"
        aria-labelledby="tab-baru"
        :hidden="activeTab !== 'baru'"
      >
        <div v-if="formServerError" class="error-banner" role="alert">
          <div class="error-banner-body">
            <strong>Gagal Menyimpan Pasien</strong>
            <p>{{ formServerError }}</p>
          </div>
        </div>

        <form id="form" novalidate @submit.prevent="handleSubmit">
          <div class="field">
            <label for="rm">
              Nomor Rekam Medis <span class="req" aria-hidden="true">*</span>
              <span class="sr">(wajib)</span>
            </label>
            <input
              id="rm"
              ref="rmInput"
              v-model="rm"
              class="control rm-input"
              name="rm"
              type="text"
              placeholder="RM-XXXX"
              autocomplete="off"
              required
              :aria-invalid="Boolean(rmErr)"
              aria-describedby="rm-err"
              @blur="validRM"
              @input="onRmInput"
            />
            <p id="rm-err" class="err" :hidden="!rmErr">{{ rmErr }}</p>
          </div>

          <div class="field">
            <label for="nama">Inisial Nama <span class="opt">(opsional)</span></label>
            <input
              id="nama"
              v-model="nama"
              class="control"
              name="nama"
              type="text"
              placeholder="Contoh: Tn. S"
              autocomplete="off"
              aria-describedby="nama-hint"
            />
            <p id="nama-hint" class="hint">
              Cukup inisial, boleh dikosongkan untuk menjaga privasi pasien.
            </p>
          </div>

          <div class="row">
            <div class="field">
              <label for="usia">Usia <span class="opt">(tahun, opsional)</span></label>
              <input
                id="usia"
                ref="usiaInput"
                v-model="usia"
                class="control"
                name="usia"
                type="number"
                inputmode="numeric"
                min="0"
                max="120"
                :aria-invalid="Boolean(usiaErr)"
                aria-describedby="usia-err"
                @input="validUsia"
              />
              <p id="usia-err" class="err" :hidden="!usiaErr">{{ usiaErr }}</p>
            </div>

            <div class="field">
              <label for="jk">Jenis Kelamin <span class="opt">(opsional)</span></label>
              <select id="jk" v-model="jk" class="control" name="jk">
                <option value="">Pilih Jenis Kelamin</option>
                <option value="Laki-laki">Laki-laki</option>
                <option value="Perempuan">Perempuan</option>
              </select>
            </div>
          </div>

          <div class="field field-lokasi">
            <label for="lokasi">Lokasi Ulkus <span class="opt">(opsional)</span></label>
            <input
              id="lokasi"
              v-model="lokasi"
              class="control"
              name="lokasi"
              type="text"
              list="lokasi-list"
              placeholder="Contoh: Telapak kaki kanan"
              autocomplete="off"
            />
            <datalist id="lokasi-list">
              <option v-for="loc in LOKASI_OPTIONS" :key="loc" :value="loc" />
            </datalist>
          </div>

          <div id="consent-box" class="consent" :class="{ invalid: Boolean(consentErr) }">
            <label class="consent-label" for="consent">
              <input
                id="consent"
                ref="consentInput"
                v-model="consent"
                type="checkbox"
                name="consent"
                required
                :aria-invalid="Boolean(consentErr)"
                aria-describedby="consent-err"
                @change="onConsentChange"
              />
              <span>
                Pasien/keluarga telah memberikan persetujuan (<em>informed consent</em>) untuk
                dokumentasi foto luka dalam rekam medis.
                <span class="req" aria-hidden="true">*</span>
                <span class="sr">(wajib)</span>
              </span>
            </label>
            <p id="consent-err" class="err" role="alert" :hidden="!consentErr">{{ consentErr }}</p>
          </div>

          <div class="form-actions">
            <p class="note">Setelah disimpan, Anda akan diarahkan ke halaman unggah foto.</p>
            <button class="btn" type="submit" :disabled="isSubmitting">
              Simpan dan Lanjut <span class="arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </form>
      </section>
    </main>
  </div>
</template>

<style scoped>
.h2-page {
  min-height: 100dvh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: var(--fs-md);
  line-height: 1.5;
}

a {
  color: inherit;
  text-decoration: none;
}

h1,
h2,
h3,
p {
  margin: 0;
}

:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
  border-radius: 3px;
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
  transition: top var(--dur);
}

.skip-link:focus {
  top: 10px;
}

/* Top bar */
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
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-right: auto;
}

.brand-mark {
  width: 32px;
  height: 32px;
  border: 1.5px solid var(--navy);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--navy);
  font-weight: 600;
  font-size: 18px;
  line-height: 1;
  flex: none;
}

.brand-name {
  display: block;
  font-size: 16px;
  font-weight: 650;
  color: var(--navy);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.brand-sub {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.2;
}

/* Penanda sistem aman (dari GET /api/v1/health) */
.secure {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 10px;
  background: var(--green-soft);
  border: 1px solid var(--green-border);
  border-radius: 999px;
  color: #14532d;
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1.3;
  white-space: nowrap;
}

.secure .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
  flex: none;
  box-shadow: 0 0 0 3px rgba(21, 128, 61, 0.15);
}

.secure.offline {
  background: var(--error-soft);
  border-color: var(--error-border);
  color: #991b1b;
}

.secure.offline .dot {
  background: var(--error);
  box-shadow: 0 0 0 3px rgba(185, 28, 28, 0.15);
}

.secure.pending {
  background: var(--band);
  border-color: var(--border-strong);
  color: var(--text-2);
}

.secure.pending .dot {
  background: var(--text-muted);
  box-shadow: none;
}

.secure svg {
  width: 14px;
  height: 14px;
  flex: none;
}

.secure .short {
  display: none;
}

.topnav {
  display: flex;
  align-self: stretch;
  gap: 8px;
}

.topnav a {
  display: flex;
  align-items: center;
  padding: 0 14px;
  font-size: 14px;
  color: var(--text-2);
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
  left: 14px;
  right: 14px;
  bottom: -1px;
  height: 2px;
  background: var(--teal);
}

/* Page */
.main-container {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 24px 72px;
}

.page-head h1 {
  font-size: 28px;
  line-height: 1.2;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--navy);
}

.page-head p {
  margin-top: 8px;
  color: var(--text-2);
  font-size: 15px;
}

/* Error Banner */
.error-banner {
  margin-top: 20px;
  margin-bottom: 16px;
  padding: 16px 18px;
  background: var(--error-soft);
  border: 1px solid var(--error-border);
  border-left: 4px solid var(--error);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.error-banner-body strong {
  display: block;
  color: #991b1b;
  font-size: 14px;
  font-weight: 650;
}

.error-banner-body p {
  margin-top: 4px;
  color: #7f1d1d;
  font-size: 13.5px;
}

.btn-retry {
  background: #991b1b !important;
  min-height: 38px !important;
  padding: 0 14px !important;
  font-size: 13px !important;
}

/* Tabs */
.tabs {
  position: relative;
  display: flex;
  gap: 28px;
  margin-top: 28px;
  border-bottom: 1px solid var(--border);
}

.tab-indicator {
  position: absolute;
  left: 0;
  bottom: -1px;
  height: 2px;
  background: var(--teal);
  border-radius: 2px;
  transition:
    transform 280ms cubic-bezier(0.2, 0, 0, 1),
    width 280ms cubic-bezier(0.2, 0, 0, 1),
    opacity 150ms;
  pointer-events: none;
}

.tab {
  font: inherit;
  font-size: 15px;
  color: var(--text-2);
  background: none;
  border: 0;
  padding: 12px 2px;
  margin-bottom: -1px;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  min-height: 48px;
  transition:
    color var(--dur),
    border-color var(--dur);
}

.tab:hover {
  color: var(--navy);
}

.tab[aria-selected='true'] {
  color: var(--navy);
  font-weight: 650;
}

.panel {
  padding-top: 24px;
}

.panel[hidden] {
  display: none;
}

.panel.enter {
  animation: fade var(--dur) ease both;
}

@keyframes fade {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

/* Search (WCAG 1.4.11 Non-Text Contrast >= 3.0:1 via --border-control) */
.search {
  position: relative;
}

.search > svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  color: var(--text-muted);
  pointer-events: none;
}

.search input {
  width: 100%;
  height: 44px;
  padding: 0 44px 0 38px;
  font: inherit;
  font-size: 14px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border-control);
  border-radius: var(--radius);
  transition:
    border-color var(--dur),
    box-shadow var(--dur);
}

.search input::placeholder {
  color: var(--text-muted);
}

.search input::-webkit-search-cancel-button {
  display: none;
}

.clear {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  width: 36px;
  height: 36px;
  border: 0;
  background: none;
  border-radius: var(--radius);
  color: var(--text-muted);
  cursor: pointer;
  display: none;
  place-items: center;
}

.clear.show {
  display: grid;
}

.clear:hover {
  background: var(--bg);
  color: var(--navy);
}

.clear svg {
  width: 16px;
  height: 16px;
}

.count {
  margin: 12px 0 10px;
  font-size: 13px;
  color: var(--text-muted);
}

/* Cards */
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.card {
  position: relative;
  cursor: pointer;
  min-height: 96px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-areas:
    'main badge'
    'main action';
  column-gap: 20px;
  row-gap: 12px;
  align-items: start;
  transition:
    border-color var(--dur),
    box-shadow var(--dur),
    transform var(--dur);
  -webkit-tap-highlight-color: rgba(31, 99, 104, 0.12);
}

.card:hover {
  border-color: var(--border-control);
  box-shadow: 0 3px 12px rgba(15, 41, 66, 0.08);
}

.card:active {
  background: #fbfcfd;
}

/* Loaded cards settle in one after another (capped at 7 steps so long lists stay fast). */
.card:not(.skeleton-card) {
  animation: card-in 320ms cubic-bezier(0.2, 0, 0, 1) both;
  animation-delay: calc(var(--i, 0) * 45ms);
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.card:has(a:focus-visible) {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}

/* Skeleton Loader Cards */
.skeleton-card {
  cursor: default;
  pointer-events: none;
  border-color: var(--border);
}

.skel-line,
.skel-pill,
.skel-btn {
  display: inline-block;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.skel-badge {
  grid-area: badge;
  justify-self: end;
  width: 210px;
  height: 24px;
  border-radius: 999px;
}

.skel-rm {
  width: 88px;
  height: 20px;
}

.skel-name {
  width: 56px;
  height: 16px;
}

.skel-attrs {
  display: block;
  margin-top: 8px;
  width: 220px;
  height: 14px;
}

.skel-history {
  display: block;
  margin-top: 10px;
  width: 170px;
  height: 13px;
}

.skel-btn {
  grid-area: action;
  justify-self: end;
  align-self: end;
  width: 126px;
  height: 44px;
  border-radius: var(--radius);
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.card-main {
  grid-area: main;
  min-width: 0;
}

.rm-line {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.rm {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-size: 18px;
  font-weight: 700;
  color: var(--navy);
  letter-spacing: 0.01em;
}

.nama {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.attrs {
  margin-top: 4px;
  font-size: 14px;
  color: var(--text-2);
}

.attrs span + span::before {
  content: '·';
  margin: 0 8px;
  color: var(--border-control);
}

.history {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-muted);
}

.history strong {
  color: var(--text-2);
  font-weight: 600;
}

.badge {
  grid-area: badge;
  justify-self: end;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
}

.badge svg {
  width: 13px;
  height: 13px;
  flex: none;
}

.badge.good {
  background: var(--teal-soft);
  color: var(--teal);
}

.badge.warn {
  background: var(--amber-soft);
  color: var(--amber);
}

.badge.neutral {
  background: var(--band);
  color: var(--navy);
}

.badge.new {
  background: var(--band);
  color: var(--text-2);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 18px;
  background: var(--navy);
  color: #fff;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  border: 0;
  border-radius: var(--radius);
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color var(--dur),
    transform var(--dur);
}

.btn:hover {
  background: var(--navy-hover);
}

.btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.card-actions {
  grid-area: action;
  justify-self: end;
  align-self: end;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.card-primary-btn {
  grid-area: action;
  justify-self: end;
  align-self: end;
}

.btn-secondary {
  position: relative;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 14px;
  background: var(--surface);
  color: var(--navy);
  border: 1px solid var(--border-control);
  border-radius: var(--radius);
  font-size: 13.5px;
  font-weight: 600;
  white-space: nowrap;
  transition:
    background-color var(--dur),
    border-color var(--dur),
    color var(--dur);
}

.btn-secondary:hover {
  background: var(--teal-soft);
  border-color: var(--teal);
  color: var(--teal);
}

.card-primary-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--radius-lg);
  z-index: 1;
}

.card:hover .card-primary-btn {
  background: var(--navy-hover);
}

.card:hover .card-primary-btn .arrow {
  transform: translateX(2px);
}

.arrow {
  display: inline-block;
  transition: transform var(--dur);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  text-align: center;
  padding: 36px 16px;
  background: var(--surface);
  border: 1px dashed var(--border-control);
  border-radius: var(--radius-lg);
  color: var(--text-2);
  font-size: 14px;
}

.empty[hidden] {
  display: none;
}

/* Form */
form {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
}

.field + .field {
  margin-top: 18px;
}

.field-lokasi {
  margin-top: 18px;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 18px;
}

.row .field + .field {
  margin-top: 0;
}

label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 6px;
}

.opt {
  font-weight: 400;
  color: var(--text-muted);
  font-size: 13px;
}

.req {
  color: var(--error);
}

/* Form inputs meet WCAG 1.4.11 Non-Text Contrast (>= 3.0:1) via --border-control */
input.control,
select.control {
  width: 100%;
  height: 44px;
  padding: 0 12px;
  font: inherit;
  font-size: 14px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border-control);
  border-radius: var(--radius);
  transition:
    border-color var(--dur),
    box-shadow var(--dur);
}

.rm-input {
  font-family: var(--mono);
}

input.control:focus,
select.control:focus,
.search input:focus {
  outline: none;
  border-color: var(--navy);
  box-shadow: 0 0 0 2px var(--navy);
}

input.control:focus-visible,
select.control:focus-visible,
.search input:focus-visible {
  outline: none;
}

.control[aria-invalid='true'] {
  border-color: var(--error);
}

.hint {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.err {
  margin-top: 6px;
  font-size: 13px;
  color: var(--error);
  font-weight: 500;
}

.err[hidden] {
  display: none;
}

/* Informed consent */
.consent {
  margin-top: 22px;
  padding: 16px;
  background: var(--teal-soft);
  border: 1px solid #99c2c4;
  border-radius: var(--radius-lg);
}

.consent.invalid {
  background: var(--error-soft);
  border-color: var(--error-border);
}

.consent-label {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin: 0;
  font-weight: 500;
  font-size: 14px;
  line-height: 1.5;
  cursor: pointer;
}

.consent-label input {
  flex: none;
  width: 22px;
  height: 22px;
  margin: 1px 0 0;
  accent-color: var(--navy);
  cursor: pointer;
}

.consent-label input:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}

.consent .err {
  margin-left: 34px;
}

.form-actions {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.form-actions .note {
  font-size: 13px;
  color: var(--text-muted);
  max-width: 340px;
}

.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

@media (max-width: 760px) {
  .secure .full {
    display: none;
  }
  .secure .short {
    display: inline;
  }
}

@media (max-width: 640px) {
  .topbar-in {
    padding: 10px 16px;
    flex-wrap: wrap;
    row-gap: 6px;
  }
  .brand-sub {
    display: none;
  }
  .topnav {
    align-self: center;
  }
  .topnav a {
    padding: 0 10px;
    min-height: 44px;
  }
  .topnav a[aria-current='page']::after {
    left: 10px;
    right: 10px;
  }
  .main-container {
    padding: 28px 16px 56px;
  }
  .page-head h1 {
    font-size: 24px;
  }
  .card {
    grid-template-columns: 1fr;
    grid-template-areas:
      'badge'
      'main'
      'action';
    row-gap: 12px;
  }
  .badge,
  .skel-badge {
    justify-self: start;
  }
  .card-actions,
  .card-primary-btn,
  .skel-btn {
    width: 100%;
    justify-self: stretch;
  }
  .card-actions .btn-secondary {
    flex: 1;
  }
  .row {
    grid-template-columns: 1fr;
  }
  .row .field + .field {
    margin-top: 0;
  }
  form {
    padding: 18px 16px;
  }
  .form-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .form-actions .btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .secure .short {
    display: none;
  }
  .secure {
    padding: 6px 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>
