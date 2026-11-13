<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { formatDateID, formatFileSize } from '@/utils/formatters'

interface Props {
  file: File
  previewUrl: string
  isFollowUp: boolean
  nextVisitNumber: number
  visitDate: string
  refImageUrl: string
  refLabel: string
  refVisitDate: string
  isSubmitting: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  replace: []
  announce: [message: string]
}>()

const isOverlayOn = ref(true)
const opacity = ref(40)
const compareView = ref<'overlay' | 'side'>('overlay')
const replaceBtnRef = ref<HTMLButtonElement | null>(null)

const canUseOverlay = computed(() => props.isFollowUp && Boolean(props.refImageUrl))
const showGhost = computed(
  () => canUseOverlay.value && compareView.value === 'overlay' && isOverlayOn.value,
)

function resetOverlay() {
  isOverlayOn.value = true
  opacity.value = 40
  compareView.value = 'overlay'
}

watch(
  () => props.previewUrl,
  () => {
    resetOverlay()
  },
)

function toggleOverlay() {
  if (compareView.value === 'side') {
    compareView.value = 'overlay'
    isOverlayOn.value = true
    emit('announce', 'Overlay foto acuan ditampilkan.')
    return
  }
  isOverlayOn.value = !isOverlayOn.value
  emit(
    'announce',
    isOverlayOn.value ? 'Overlay foto acuan ditampilkan.' : 'Overlay foto acuan disembunyikan.',
  )
}

function toggleSideView() {
  compareView.value = compareView.value === 'overlay' ? 'side' : 'overlay'
  emit(
    'announce',
    compareView.value === 'side'
      ? 'Menampilkan foto acuan dan foto baru secara berdampingan.'
      : 'Menampilkan pratinjau dengan overlay foto acuan.',
  )
}

function focusReplace() {
  replaceBtnRef.value?.focus()
}

defineExpose({ focusReplace, resetOverlay })
</script>

<template>
  <div id="preview" class="preview">
    <!-- Tampilan utama: bingkai tunggal dengan ghost overlay -->
    <div v-if="compareView === 'overlay'" class="frame">
      <div id="stack" class="stack" :style="{ '--ghost': String(opacity / 100) }">
        <img
          id="img"
          class="main"
          :src="previewUrl"
          alt="Pratinjau foto luka yang akan diproses"
        />
        <img
          v-if="showGhost"
          id="ghost"
          class="ghost"
          :src="refImageUrl"
          alt=""
          aria-hidden="true"
        />
      </div>
    </div>

    <!-- Tampilan alternatif (PRD v2 10.3 / PRD v3 Bag. 4): berdampingan -->
    <div v-else id="ref-side-view" class="ref-side-grid">
      <figure class="compare-card">
        <div class="compare-head">
          <span>Foto Acuan ({{ refLabel }})</span>
          <small>{{ formatDateID(refVisitDate) }}</small>
        </div>
        <div class="compare-frame">
          <img :src="refImageUrl" :alt="`Foto acuan ${refLabel}`" />
        </div>
      </figure>

      <figure class="compare-card">
        <div class="compare-head">
          <span>Foto Baru (Kunjungan ke-{{ nextVisitNumber }})</span>
          <small>{{ formatDateID(visitDate) }}</small>
        </div>
        <div class="compare-frame">
          <img :src="previewUrl" alt="Foto baru yang dipilih untuk dibandingkan" />
        </div>
      </figure>
    </div>

    <!-- Kontrol ghost overlay: disembunyikan pada kunjungan 1 atau bila tidak ada citra acuan -->
    <div v-if="canUseOverlay" id="ghostCtl" class="ghost-ctl">
      <button
        id="gsw"
        type="button"
        class="swbtn"
        role="switch"
        :aria-checked="isOverlayOn && compareView === 'overlay'"
        @click="toggleOverlay"
      >
        <span class="track" aria-hidden="true"></span>
        <span>Tampilkan overlay foto acuan</span>
      </button>

      <div class="op">
        <label for="gop">Transparansi overlay</label>
        <input
          id="gop"
          v-model.number="opacity"
          type="range"
          min="0"
          max="80"
          step="5"
          :disabled="!isOverlayOn || compareView === 'side'"
          aria-describedby="ghost-note"
        />
        <output id="gout" for="gop">{{ opacity }}%</output>
      </div>

      <button
        id="btn-side-toggle"
        type="button"
        class="btn btn-secondary btn-sm"
        @click="toggleSideView"
      >
        {{ compareView === 'overlay' ? 'Tampilan berdampingan' : 'Kembali ke overlay' }}
      </button>

      <p id="ghost-note" class="ghost-note">
        Samakan ukuran bagian tubuh yang tidak berubah (misalnya lebar pergelangan atau sisi kaki),
        bukan tepi luka. Overlay hanya alat bantu visual dan tidak mengubah foto yang diproses.
      </p>
    </div>

    <div class="fileinfo">
      <div>
        <div id="fname" class="fname">{{ file.name }}</div>
        <div id="fsize" class="fsize">{{ formatFileSize(file.size) }}</div>
      </div>
      <div class="fileinfo-actions">
        <span class="fcheck" aria-hidden="true">✓ Foto siap</span>
        <button
          id="replace"
          ref="replaceBtnRef"
          class="btn btn-secondary"
          type="button"
          :disabled="isSubmitting"
          @click="emit('replace')"
        >
          Ganti Foto
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview {
  margin-top: 0;
}
.frame {
  background: rgba(15, 23, 42, 0.05);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  justify-content: center;
  padding: 12px;
}
.stack {
  position: relative;
  display: inline-block;
  line-height: 0;
  max-width: 100%;
}
.stack img.main {
  display: block;
  max-width: 100%;
  max-height: 420px;
  width: auto;
  height: auto;
  border-radius: 4px;
}
.stack img.ghost {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 4px;
  pointer-events: none;
  opacity: var(--ghost, 0.4);
}

.ref-side-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.compare-card {
  margin: 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
}
.compare-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--navy);
}
.compare-head small {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
}
.compare-frame {
  background: rgba(15, 23, 42, 0.05);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  aspect-ratio: 4 / 3;
  display: grid;
  place-items: center;
}
.compare-frame img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.ghost-ctl {
  margin-top: 12px;
  padding: 12px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  gap: 12px 24px;
  align-items: center;
  flex-wrap: wrap;
}
.swbtn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--navy);
  background: none;
  border: 0;
  cursor: pointer;
  padding: 0;
}
.swbtn .track {
  width: 40px;
  height: 22px;
  border-radius: 999px;
  background: #94a3b8;
  position: relative;
  transition: background-color var(--dur);
  flex: none;
}
.swbtn .track::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform var(--dur);
}
.swbtn[aria-checked='true'] .track {
  background: var(--teal);
}
.swbtn[aria-checked='true'] .track::after {
  transform: translateX(18px);
}

.op {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-2);
}
.op input[type='range'] {
  width: 180px;
  accent-color: var(--navy);
}
.op output {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  color: var(--navy);
  font-weight: 700;
  min-width: 3.2ch;
  display: inline-block;
}
.ghost-note {
  width: 100%;
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted);
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
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--navy);
  cursor: pointer;
}
.btn:hover:not(:disabled) {
  border-color: var(--navy);
  background: var(--bg);
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-sm {
  min-height: 36px;
  padding: 0 12px;
  font-size: 13px;
}

@media (max-width: 640px) {
  .ref-side-grid {
    grid-template-columns: 1fr;
  }
  .op {
    width: 100%;
  }
  .op input[type='range'] {
    flex: 1;
    width: auto;
  }
}
@media (prefers-reduced-motion: reduce) {
  .swbtn .track,
  .swbtn .track::after {
    transition: none;
  }
}
</style>
