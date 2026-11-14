<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import type { VisitRecord } from '@/types/patient'

interface Props {
  visit: VisitRecord
  isBaseline: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  notify: [message: string]
}>()

const activeTab = ref<'clinician' | 'patient'>('clinician')
const tabClinRef = ref<HTMLButtonElement | null>(null)
const tabPatRef = ref<HTMLButtonElement | null>(null)

const sourceTitle = computed(() => {
  if (props.visit.narrative_source === 'llm') {
    return 'AI generatif tervalidasi (llm)'
  }
  if (props.visit.narrative_source === 'template_fallback') {
    return 'Templat deterministik sistem (template_fallback)'
  }
  return 'Belum tersedia'
})

const sourceDescription = computed(() => {
  if (props.visit.narrative_source === 'llm') {
    return 'Disusun otomatis dari parameter numerik terhitung (A₀, Aₜ, ΔA, PAC, status tren) tanpa mengirimkan foto luka maupun identitas pasien.'
  }
  if (props.visit.narrative_source === 'template_fallback') {
    return 'Disusun otomatis menggunakan templat baku terverifikasi dari parameter numerik terhitung (A₀, Aₜ, ΔA, PAC, status tren).'
  }
  return 'Narasi belum dibuat untuk kunjungan ini.'
})

function selectTab(tab: 'clinician' | 'patient', moveFocus = false) {
  activeTab.value = tab
  if (!moveFocus) return
  nextTick(() => {
    if (tab === 'clinician') tabClinRef.value?.focus()
    else tabPatRef.value?.focus()
  })
}

function onTabKeydown(e: KeyboardEvent, current: 'clinician' | 'patient') {
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    selectTab(current === 'clinician' ? 'patient' : 'clinician', true)
  } else if (e.key === 'Home') {
    e.preventDefault()
    selectTab('clinician', true)
  } else if (e.key === 'End') {
    e.preventDefault()
    selectTab('patient', true)
  }
}

async function copyNarrative(text: string | null | undefined, successMsg: string) {
  if (!text) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      emit('notify', successMsg)
      return
    }
  } catch {
    // Gunakan fallback di bawah bila Clipboard API tidak tersedia di konteks browser
  }
  emit('notify', 'Gagal menyalin otomatis. Silakan sorot teks lalu salin manual.')
}
</script>

<template>
  <section
    v-if="isBaseline"
    id="narrBaseline"
    class="panel narr-base"
    role="region"
    aria-label="Informasi narasi kunjungan awal"
  >
    <h2>Kunjungan Awal (Baseline A₀) — Tanpa Narasi Perbandingan</h2>
    <p class="base-desc">
      Kunjungan pertama digunakan untuk menetapkan luas acuan awal (A₀). Catatan klinis
      longitudinal dan penjelasan perkembangan luka untuk pasien baru disusun mulai kunjungan kedua
      setelah perhitungan PAC tersedia.
    </p>
    <div id="staticWoundCareGuide" class="care-guide">
      <b>Panduan Umum Perawatan Luka</b>
      <p>
        Jaga balutan luka tetap bersih dan kering, kurangi tumpuan atau tekanan berlebih pada area
        ulkus, serta patuhi jadwal kontrol rutin bersama perawat atau dokter.
      </p>
    </div>
    <p class="base-disclaimer">
      Catatan: Hasil merupakan estimasi sistem berbasis citra visual, bukan diagnosis medis.
    </p>
  </section>

  <section v-else id="tabsCard" class="panel tabs-card" aria-label="Narasi hasil pemeriksaan">
    <div class="tablist" role="tablist" aria-label="Narasi hasil pemeriksaan">
      <button
        id="tab-catatan"
        ref="tabClinRef"
        class="tab"
        role="tab"
        type="button"
        aria-controls="panel-catatan"
        :aria-selected="activeTab === 'clinician'"
        :tabindex="activeTab === 'clinician' ? 0 : -1"
        @click="selectTab('clinician')"
        @keydown="onTabKeydown($event, 'clinician')"
      >
        Catatan Klinis
      </button>
      <button
        id="tab-pasien"
        ref="tabPatRef"
        class="tab"
        role="tab"
        type="button"
        aria-controls="panel-pasien"
        :aria-selected="activeTab === 'patient'"
        :tabindex="activeTab === 'patient' ? 0 : -1"
        @click="selectTab('patient')"
        @keydown="onTabKeydown($event, 'patient')"
      >
        Penjelasan untuk Pasien
      </button>
    </div>

    <div
      id="panel-catatan"
      class="tabpanel"
      role="tabpanel"
      aria-labelledby="tab-catatan"
      :hidden="activeTab !== 'clinician'"
    >
      <p v-if="visit.clinician_notes" id="clinicianNotesText" class="narr-body">
        {{ visit.clinician_notes }}
      </p>
      <p v-else id="clinicianNotesEmpty" class="narr-empty">
        Catatan klinis belum tersedia untuk kunjungan ini.
      </p>

      <div v-if="visit.clinician_notes" class="copy-row">
        <button
          id="btnCopyClinician"
          class="btn btn-secondary btn-sm"
          type="button"
          @click="copyNarrative(visit.clinician_notes, 'Catatan klinis disalin ke papan klip.')"
        >
          Salin Catatan Klinis
        </button>
      </div>
    </div>

    <div
      id="panel-pasien"
      class="tabpanel"
      role="tabpanel"
      aria-labelledby="tab-pasien"
      :hidden="activeTab !== 'patient'"
    >
      <p v-if="visit.patient_narrative" id="patientNarrativeText" class="narr-body">
        {{ visit.patient_narrative }}
      </p>
      <p v-else id="patientNarrativeEmpty" class="narr-empty">
        Penjelasan untuk pasien belum tersedia untuk kunjungan ini.
      </p>

      <div id="staticWoundCareGuide" class="care-guide">
        <b>Panduan Umum Perawatan Luka</b>
        <p>
          Jaga balutan luka tetap bersih dan kering, kurangi tumpuan atau tekanan berlebih pada area
          ulkus, serta patuhi jadwal kontrol rutin bersama perawat atau dokter.
        </p>
      </div>

      <div v-if="visit.patient_narrative" class="copy-row">
        <button
          id="btnCopyPatient"
          class="btn btn-secondary btn-sm"
          type="button"
          @click="copyNarrative(visit.patient_narrative, 'Penjelasan untuk pasien disalin ke papan klip.')"
        >
          Salin Penjelasan Pasien
        </button>
      </div>
    </div>

    <div class="source">
      <div class="source-head">
        <span><b>Sumber narasi:</b> {{ sourceTitle }}</span>
        <span
          v-if="visit.narrative_source"
          id="narrativeSourceBadge"
          class="src-badge"
          :class="visit.narrative_source === 'llm' ? 'llm' : 'fallback'"
        >
          {{ visit.narrative_source }}
        </span>
      </div>
      <p>{{ sourceDescription }}</p>
      <p class="src-disclaimer">
        Hasil merupakan estimasi sistem berbasis citra visual, bukan diagnosis medis. Periksa kembali
        sebelum dijadikan catatan resmi.
      </p>
    </div>
  </section>
</template>

<style scoped>
.panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
.narr-base { margin-top: 24px; padding: 20px 22px; }
.narr-base h2 { margin: 0; font-size: 16px; font-weight: 650; color: var(--navy); }
.base-desc { margin: 8px 0 0; font-size: 14.5px; line-height: 1.65; color: var(--text-2); max-width: 880px; }
.base-disclaimer { margin: 12px 0 0; font-size: 12.5px; color: var(--muted); }
.tabs-card { margin-top: 24px; overflow: hidden; }
.tablist { display: flex; gap: 24px; padding: 0 22px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.tab {
  font: inherit; font-size: 15px; color: var(--text-2); background: none; border: 0;
  padding: 14px 2px; margin-bottom: -1px; border-bottom: 2px solid transparent;
  cursor: pointer; min-height: 48px; transition: color var(--dur), border-color var(--dur);
}
.tab:hover { color: var(--navy); }
.tab[aria-selected='true'] { color: var(--navy); font-weight: 650; border-bottom-color: var(--teal); }
.tabpanel { padding: 20px 22px 16px; }
.narr-body { margin: 0; font-size: 15px; line-height: 1.75; color: var(--text); max-width: 880px; white-space: pre-line; }
.narr-empty { margin: 0; font-size: 14px; color: var(--muted); font-style: italic; }
.care-guide {
  margin-top: 14px; padding: 12px 14px; background: var(--teal-soft);
  border: 1px solid #bfdcdc; border-radius: 8px; max-width: 880px;
}
.care-guide b { display: block; font-size: 13px; color: var(--navy); margin-bottom: 3px; }
.care-guide p { margin: 0; font-size: 13.5px; line-height: 1.6; color: var(--text-2); }
.copy-row { margin-top: 14px; }
.btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 40px; padding: 0 14px; font: inherit; font-size: 13px; font-weight: 600;
  border-radius: 6px; border: 1px solid var(--border-strong); background: var(--surface);
  color: var(--navy); cursor: pointer;
}
.btn:hover { border-color: var(--navy); background: var(--bg); }
.source { margin: 0 22px 20px; padding-top: 14px; border-top: 1px solid var(--border); max-width: 880px; }
.source-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12.5px; color: var(--text); }
.src-badge {
  font-family: var(--mono); font-size: 11.5px; font-weight: 700; padding: 2px 8px;
  border-radius: 999px; border: 1px solid;
}
.src-badge.llm { color: var(--green); background: var(--green-bg); border-color: var(--green-bd); }
.src-badge.fallback { color: var(--navy); background: #f1f5f9; border-color: var(--border-strong); }
.source p { margin: 6px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--text-2); }
.source .src-disclaimer { color: var(--muted); }
@media (max-width: 760px) {
  .tablist { padding: 0 16px; gap: 16px; }
  .tabpanel { padding: 16px 16px 14px; }
  .source { margin: 0 16px 16px; }
}
</style>
