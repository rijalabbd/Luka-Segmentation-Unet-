<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { VisitRecord } from '@/types/patient'
import { formatDateID } from '@/utils/formatters'

interface Props {
  isFollowUp: boolean
  activeTab: 'baseline' | 'latest'
  hasDistinctLatest: boolean
  activeVisit: VisitRecord | null
  activeImageUrl: string
  activeOverlayUrl: string
  activeDisplayUrl: string
  showContour: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:activeTab': [tab: 'baseline' | 'latest']
  'update:showContour': [value: boolean]
}>()

const isZoomOpen = ref(false)
const tabBaseRef = ref<HTMLButtonElement | null>(null)
const tabLastRef = ref<HTMLButtonElement | null>(null)
const zoomOpenBtnRef = ref<HTMLButtonElement | null>(null)
const zoomCloseBtnRef = ref<HTMLButtonElement | null>(null)

const isLatestTab = computed(() => props.activeTab === 'latest' && props.hasDistinctLatest)

const captionText = computed(() => {
  if (!props.activeVisit) return ''
  const visitLabel = isLatestTab.value
    ? `Kunjungan ke-${props.activeVisit.visit_index ?? '?'}`
    : 'Kunjungan awal'
  return `(${visitLabel} · ${formatDateID(props.activeVisit.visit_date)} · Luas relatif: ${props.activeVisit.area_pct.toFixed(2)}%)`
})

const helpText = computed(() => {
  return isLatestTab.value
    ? 'Foto kunjungan terakhir sebagai pembanding tambahan. Acuan utama tetap foto kunjungan awal.'
    : 'Samakan jarak dan sudut kamera dengan foto ini. PAC dihitung terhadap kunjungan awal, sehingga foto baseline adalah acuan utama.'
})

const zoomTitle = computed(() => {
  if (!props.activeVisit) return 'Foto Acuan'
  const prefix = isLatestTab.value
    ? `Acuan Kunjungan ke-${props.activeVisit.visit_index ?? '?'}`
    : 'Acuan Kunjungan Awal (Baseline)'
  return `${prefix} · ${formatDateID(props.activeVisit.visit_date)}`
})

function selectTab(tab: 'baseline' | 'latest', moveFocus = false) {
  emit('update:activeTab', tab)
  if (!moveFocus) return
  nextTick(() => {
    if (tab === 'latest' && props.hasDistinctLatest) {
      tabLastRef.value?.focus()
    } else {
      tabBaseRef.value?.focus()
    }
  })
}

function onTabKeydown(e: KeyboardEvent, current: 'baseline' | 'latest') {
  if (!props.hasDistinctLatest) return
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    selectTab(current === 'baseline' ? 'latest' : 'baseline', true)
  } else if (e.key === 'Home') {
    e.preventDefault()
    selectTab('baseline', true)
  } else if (e.key === 'End') {
    e.preventDefault()
    selectTab('latest', true)
  }
}

function openZoom() {
  if (!props.activeDisplayUrl) return
  isZoomOpen.value = true
}

function closeZoom() {
  isZoomOpen.value = false
  nextTick(() => {
    zoomOpenBtnRef.value?.focus()
  })
}

function onZoomKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    closeZoom()
  } else if (e.key === 'Tab') {
    e.preventDefault()
    zoomCloseBtnRef.value?.focus()
  }
}

watch(isZoomOpen, (open) => {
  if (open) {
    nextTick(() => {
      zoomCloseBtnRef.value?.focus()
    })
  }
})
</script>

<template>
  <!-- Kunjungan 1: keterangan baseline -->
  <div v-if="!isFollowUp" id="ref-first" class="ref-first">
    <b>Kunjungan awal:</b> foto ini akan menjadi acuan kunjungan berikutnya. Jika ada penggaris,
    letakkan di dekat luka dan sebidang dengan permukaan luka agar kalibrasi opsional dapat
    dilakukan di halaman hasil.
  </div>

  <!-- Kunjungan >= 2: panel foto acuan bertab -->
  <section v-else id="ref" class="ref" aria-labelledby="ref-t">
    <div id="refTabs" class="ref-tabs" role="tablist" aria-label="Pilih foto acuan">
      <button
        id="tab-base"
        ref="tabBaseRef"
        type="button"
        role="tab"
        data-ref="base"
        :aria-selected="!isLatestTab"
        :tabindex="!isLatestTab ? 0 : -1"
        @click="selectTab('baseline')"
        @keydown="onTabKeydown($event, 'baseline')"
      >
        Kunjungan Awal (Baseline)
      </button>
      <button
        v-if="hasDistinctLatest"
        id="tab-last"
        ref="tabLastRef"
        type="button"
        role="tab"
        data-ref="last"
        :aria-selected="isLatestTab"
        :tabindex="isLatestTab ? 0 : -1"
        @click="selectTab('latest')"
        @keydown="onTabKeydown($event, 'latest')"
      >
        Kunjungan Terakhir
      </button>
    </div>

    <div
      id="refPanel"
      role="tabpanel"
      :aria-labelledby="isLatestTab ? 'tab-last' : 'tab-base'"
    >
      <div v-if="!activeImageUrl" id="ref-unavailable" class="ref-unavailable" role="status">
        <strong>Foto acuan tidak tersedia</strong>
        <span>
          Data kunjungan ke-{{ activeVisit?.visit_index ?? 1 }} ({{
            formatDateID(activeVisit?.visit_date)
          }}) tidak menyertakan berkas citra. Gunakan panduan jarak dan sudut di samping.
        </span>
      </div>

      <div v-else class="ref-body">
        <button
          id="ref-open"
          ref="zoomOpenBtnRef"
          type="button"
          class="ref-thumb"
          :aria-label="`Perbesar foto acuan ${captionText}`"
          @click="openZoom"
        >
          <img
            id="ref-img"
            :src="activeDisplayUrl"
            :alt="`Foto luka acuan kunjungan ke-${activeVisit?.visit_index ?? 1}`"
          />
          <span class="zoom" aria-hidden="true">Perbesar</span>
        </button>

        <div class="ref-info">
          <h2 id="ref-t">
            Foto Acuan
            <span id="ref-cap">{{ captionText }}</span>
          </h2>
          <p id="ref-help">{{ helpText }}</p>

          <label v-if="activeOverlayUrl" class="contour-toggle" for="toggle-ref-contour">
            <input
              id="toggle-ref-contour"
              type="checkbox"
              :checked="showContour"
              @change="emit('update:showContour', ($event.target as HTMLInputElement).checked)"
            />
            <span>Tampilkan kontur masker acuan</span>
          </label>
        </div>
      </div>
    </div>

    <!-- Dialog perbesar foto acuan -->
    <div
      v-if="isZoomOpen && activeDisplayUrl"
      id="zoom"
      class="modal-back"
      @click.self="closeZoom"
      @keydown="onZoomKeydown"
    >
      <div class="modal wide" role="dialog" aria-modal="true" aria-labelledby="z-t">
        <div class="cap">
          <h2 id="z-t">{{ zoomTitle }}</h2>
          <button
            id="z-close"
            ref="zoomCloseBtnRef"
            class="btn btn-secondary"
            type="button"
            @click="closeZoom"
          >
            Tutup
          </button>
        </div>
        <img
          id="z-img"
          :src="activeDisplayUrl"
          :alt="`Foto luka acuan dari kunjungan ke-${activeVisit?.visit_index ?? 1}, ukuran diperbesar`"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.ref-first {
  padding: 12px 14px;
  margin-bottom: 18px;
  background: var(--teal-soft);
  border: 1px solid #bfdcdc;
  border-radius: 8px;
  font-size: 13.5px;
  color: var(--text);
}
.ref-first b {
  color: var(--navy);
}

.ref {
  padding: 12px;
  margin-bottom: 18px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.ref-tabs {
  display: inline-flex;
  gap: 2px;
  background: #eef2f6;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 3px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.ref-tabs button {
  font: inherit;
  font-size: 13px;
  color: var(--text-2);
  background: none;
  border: 0;
  border-radius: 6px;
  padding: 8px 12px;
  min-height: 40px;
  cursor: pointer;
}
.ref-tabs button:hover {
  color: var(--navy);
}
.ref-tabs button[aria-selected='true'] {
  background: var(--surface);
  color: var(--navy);
  font-weight: 650;
  box-shadow: 0 1px 3px rgba(15, 41, 66, 0.12);
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
  gap: 16px;
  align-items: center;
}

.ref-thumb {
  position: relative;
  flex: none;
  width: 132px;
  height: 99px;
  padding: 0;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  overflow: hidden;
  cursor: zoom-in;
  background: #fff;
}
.ref-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ref-thumb .zoom {
  position: absolute;
  right: 4px;
  bottom: 4px;
  background: rgba(15, 41, 66, 0.88);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 4px;
}

.ref-info h2 {
  font-size: 14px;
  font-weight: 650;
  color: var(--navy);
  line-height: 1.4;
  margin: 0;
}
.ref-info h2 span {
  display: block;
  font-weight: 500;
  color: var(--text-2);
}
.ref-info p {
  font-size: 13px;
  color: var(--text-2);
  margin: 6px 0 0;
}

.contour-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
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

.modal-back {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 50;
}
.modal.wide {
  background: #fff;
  border-radius: 10px;
  max-width: 760px;
  width: 100%;
  padding: 18px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}
.modal.wide img {
  display: block;
  width: 100%;
  max-height: 75vh;
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid var(--border);
}
.modal.wide .cap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.modal.wide .cap h2 {
  margin: 0;
  font-size: 16px;
  color: var(--navy);
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 18px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--navy);
  cursor: pointer;
}
.btn:hover {
  border-color: var(--navy);
  background: var(--bg);
}

@media (max-width: 480px) {
  .ref-body {
    flex-direction: column;
    align-items: stretch;
  }
  .ref-thumb {
    width: 100%;
    height: auto;
    aspect-ratio: 4 / 3;
  }
}
</style>
