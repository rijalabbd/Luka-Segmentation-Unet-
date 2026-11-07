<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const patientId = computed(() => String(route.params.patientId ?? ''))
const visitId = computed(() => String(route.params.visitId ?? ''))

const isRiwayat = computed(() => route.name === 'riwayat-pasien')
const isKunjungan = computed(() => route.name === 'hasil-kunjungan')
</script>

<template>
  <div class="route-stub">
    <header class="topbar">
      <div class="topbar-in">
        <RouterLink class="brand" to="/">
          <span class="brand-mark" aria-hidden="true">+</span>
          <span>
            <span class="brand-name">Dokumentasi Luka</span>
            <span class="brand-sub">Pemantauan Berkala</span>
          </span>
        </RouterLink>
        <nav class="topnav" aria-label="Navigasi utama">
          <RouterLink to="/">Beranda</RouterLink>
          <RouterLink to="/pemeriksaan" aria-current="page">Pemeriksaan</RouterLink>
        </nav>
      </div>
    </header>

    <main class="main-wrap">
      <RouterLink class="back" to="/pemeriksaan">← Kembali ke Pilih Pasien</RouterLink>

      <template v-if="isRiwayat">
        <h1>Riwayat Pemeriksaan Pasien</h1>
        <div class="patient-card">
          <div>
            <div class="p-label">Pasien terpilih (rm_code)</div>
            <div class="p-rm">{{ patientId }}</div>
          </div>
          <p class="p-note">
            Rute <code>/pasien/{{ patientId }}</code> siap untuk eksekusi Halaman 5 (Fase 4).
          </p>
        </div>
      </template>

      <template v-else-if="isKunjungan">
        <h1>Hasil Pemeriksaan Luka</h1>
        <div class="patient-card">
          <div>
            <div class="p-label">ID Kunjungan</div>
            <div class="p-rm">#{{ visitId }}</div>
          </div>
          <p class="p-note">
            Rute <code>/kunjungan/{{ visitId }}</code> siap untuk eksekusi Halaman 4 (Fase 3).
          </p>
        </div>
      </template>

      <template v-else>
        <h1>Unggah Foto dan Deteksi</h1>
        <div class="patient-card">
          <div>
            <div class="p-label">Pasien terpilih (rm_code)</div>
            <div class="p-rm">{{ patientId }}</div>
          </div>
          <p class="p-note">
            Rute <code>/pemeriksaan/{{ patientId }}/unggah</code> siap untuk eksekusi Halaman 3
            (Fase 2).
          </p>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.route-stub {
  min-height: 100dvh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
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
  border: 1.5px solid var(--navy);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--navy);
  font-weight: 600;
}
.brand-name {
  display: block;
  font-size: 16px;
  font-weight: 650;
  color: var(--navy);
}
.brand-sub {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}
.topnav {
  display: flex;
  gap: 12px;
}
.topnav a {
  text-decoration: none;
  color: var(--text-2);
  font-size: 14px;
  padding: 8px 12px;
}
.topnav a[aria-current='page'] {
  color: var(--navy);
  font-weight: 650;
}
.main-wrap {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px;
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
  color: var(--navy);
  margin: 4px 0 18px;
}
.patient-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--teal);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.p-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  font-weight: 600;
}
.p-rm {
  font-family: var(--mono);
  font-size: 24px;
  font-weight: 700;
  color: var(--navy);
}
.p-note {
  font-size: 14px;
  color: var(--text-2);
  margin: 0;
}
</style>
