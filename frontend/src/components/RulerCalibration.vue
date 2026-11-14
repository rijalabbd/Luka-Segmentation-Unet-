<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ApiError, deleteVisitCalibration, putVisitCalibration } from '@/api/patients'
import type { VisitRecord } from '@/types/patient'
import {
  displayClickToOriginalPoint,
  originalToDisplayPoint,
  type Point2D,
  validateAndComputeCalibration,
} from '@/utils/calibrationCoords'
import { formatDecimalID } from '@/utils/formatters'

interface Props {
  visit: VisitRecord
  imageUrl: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  updated: [visit: VisitRecord]
  conflict: [message: string]
  notify: [message: string]
}>()

const imgWidthPx = computed(() =>
  props.visit.img_width_px && props.visit.img_width_px > 0 ? props.visit.img_width_px : 256,
)
const imgHeightPx = computed(() =>
  props.visit.img_height_px && props.visit.img_height_px > 0 ? props.visit.img_height_px : 256,
)

const isApplied = computed(() => props.visit.measure_mode === 'calibrated')
const isLocked409 = ref(false)
const isPanelDisabled = computed(() => props.visit.status !== 'draft' || isLocked409.value)

const isDetailsOpen = ref(isApplied.value)
const p1 = ref<Point2D | null>(null)
const p2 = ref<Point2D | null>(null)
const lengthCm = ref<number>(2)
const activePoint = ref<1 | 2>(1)

const isSubmitting = ref(false)
const clickError = ref('')
const apiError = ref('')
const attemptedSubmit = ref(false)

const imgRef = ref<HTMLImageElement | null>(null)
const boxWidth = ref(0)
const boxHeight = ref(0)
let resizeObserver: ResizeObserver | null = null

function syncFromVisit(v: VisitRecord) {
  if (
    v.calib_x1 !== null &&
    v.calib_y1 !== null &&
    v.calib_x2 !== null &&
    v.calib_y2 !== null
  ) {
    p1.value = { x: v.calib_x1, y: v.calib_y1 }
    p2.value = { x: v.calib_x2, y: v.calib_y2 }
    lengthCm.value = v.calib_length_cm ?? 2
    if (v.status === 'draft' && v.measure_mode === 'calibrated') {
      isDetailsOpen.value = true
    }
  } else if (v.measure_mode === 'relative') {
    p1.value = null
    p2.value = null
    lengthCm.value = 2
  }
  clickError.value = ''
  apiError.value = ''
  attemptedSubmit.value = false
}

watch(
  () => [
    props.visit.id,
    props.visit.status,
    props.visit.measure_mode,
    props.visit.calib_x1,
    props.visit.calib_y1,
    props.visit.calib_x2,
    props.visit.calib_y2,
    props.visit.calib_length_cm,
  ],
  () => {
    syncFromVisit(props.visit)
  },
  { immediate: true },
)

function measureBox() {
  const el = imgRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  boxWidth.value = rect.width
  boxHeight.value = rect.height
}

function onDetailsToggle(e: Event) {
  const el = e.target as HTMLDetailsElement | null
  isDetailsOpen.value = Boolean(el?.open)
  if (isDetailsOpen.value) {
    nextTick(() => {
      requestAnimationFrame(measureBox)
    })
  }
}

onMounted(() => {
  if (imgRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => measureBox())
    resizeObserver.observe(imgRef.value)
  }
  window.addEventListener('resize', measureBox)
  window.visualViewport?.addEventListener('resize', measureBox)
  measureBox()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', measureBox)
  window.visualViewport?.removeEventListener('resize', measureBox)
})

const validation = computed(() =>
  validateAndComputeCalibration({
    p1: p1.value,
    p2: p2.value,
    lengthCm: Number(lengthCm.value),
    imgWidthPx: imgWidthPx.value,
    imgHeightPx: imgHeightPx.value,
    nWoundPx: props.visit.n_wound_px,
  }),
)

const dispP1 = computed(() => {
  if (!p1.value || boxWidth.value <= 0 || boxHeight.value <= 0) return null
  return originalToDisplayPoint({
    x: p1.value.x,
    y: p1.value.y,
    boxWidth: boxWidth.value,
    boxHeight: boxHeight.value,
    imgWidthPx: imgWidthPx.value,
    imgHeightPx: imgHeightPx.value,
  })
})

const dispP2 = computed(() => {
  if (!p2.value || boxWidth.value <= 0 || boxHeight.value <= 0) return null
  return originalToDisplayPoint({
    x: p2.value.x,
    y: p2.value.y,
    boxWidth: boxWidth.value,
    boxHeight: boxHeight.value,
    imgWidthPx: imgWidthPx.value,
    imgHeightPx: imgHeightPx.value,
  })
})

const visibleError = computed(() => {
  if (apiError.value) return apiError.value
  if (clickError.value) return clickError.value
  const len = Number(lengthCm.value)
  const invalidLength = Number.isNaN(len) || len <= 0 || len > 50
  if (invalidLength) {
    return 'Panjang penggaris nyata (length_cm) harus berada pada rentang (0, 50] cm.'
  }
  if ((p1.value !== null && p2.value !== null) || attemptedSubmit.value) {
    if (!validation.value.ok && validation.value.error) {
      return validation.value.error
    }
  }
  return ''
})

const statusText = computed(() => {
  if (isPanelDisabled.value) {
    return 'Panel kalibrasi tidak aktif karena kunjungan sudah final.'
  }
  if (!p1.value) {
    return 'Belum ada titik. Klik foto penggaris atau isi koordinat untuk menetapkan Titik 1.'
  }
  if (!p2.value) {
    return `Titik 1 di (${p1.value.x.toFixed(1)}, ${p1.value.y.toFixed(1)}) px. Klik foto untuk Titik 2.`
  }
  if (!validation.value.ok) {
    return `Titik 1 (${p1.value.x.toFixed(1)}, ${p1.value.y.toFixed(1)}) & Titik 2 (${p2.value.x.toFixed(1)}, ${p2.value.y.toFixed(1)}) px — belum valid.`
  }
  return `Titik 1 (${p1.value.x.toFixed(1)}, ${p1.value.y.toFixed(1)}) & Titik 2 (${p2.value.x.toFixed(1)}, ${p2.value.y.toFixed(1)}) px siap diterapkan.`
})

function handleImageClick(e: MouseEvent) {
  if (isPanelDisabled.value || isSubmitting.value || !imgRef.value) return
  const rect = imgRef.value.getBoundingClientRect()
  boxWidth.value = rect.width
  boxHeight.value = rect.height

  const conv = displayClickToOriginalPoint({
    clientX: e.clientX,
    clientY: e.clientY,
    boxRect: {
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: rect.height,
    },
    imgWidthPx: imgWidthPx.value,
    imgHeightPx: imgHeightPx.value,
  })

  apiError.value = ''
  if (!conv.ok || !conv.point) {
    clickError.value =
      'Klik berada di luar area citra (bidang kosong). Klik tepat pada gambar penggaris.'
    return
  }

  clickError.value = ''
  if (!p1.value || (p1.value && p2.value)) {
    // Klik ke-1 atau klik ke-3 memulai ulang pilihan dari Titik 1
    p1.value = conv.point
    p2.value = null
    activePoint.value = 2
    attemptedSubmit.value = false
  } else {
    p2.value = conv.point
    activePoint.value = 2
  }
}

function onStageKeydown(e: KeyboardEvent) {
  if (isPanelDisabled.value || isSubmitting.value) return
  if (e.key === '1') {
    activePoint.value = 1
    return
  }
  if (e.key === '2') {
    activePoint.value = 2
    return
  }
  const targetPoint = activePoint.value === 1 ? p1.value : p2.value
  if (!targetPoint) return

  const step = e.shiftKey ? 10 : 1
  const deltas: Record<string, [number, number] | undefined> = {
    ArrowLeft: [-step, 0],
    ArrowRight: [step, 0],
    ArrowUp: [0, -step],
    ArrowDown: [0, step],
  }
  const move = deltas[e.key]
  if (!move) return
  e.preventDefault()

  const nextPt = {
    x: Math.min(imgWidthPx.value, Math.max(0, targetPoint.x + move[0])),
    y: Math.min(imgHeightPx.value, Math.max(0, targetPoint.y + move[1])),
  }
  if (activePoint.value === 1) {
    p1.value = nextPt
  } else {
    p2.value = nextPt
  }
  clickError.value = ''
  apiError.value = ''
}

function updatePointCoord(which: 1 | 2, axis: 'x' | 'y', raw: string) {
  if (isPanelDisabled.value || isSubmitting.value) return
  const parsed = Number(raw)
  if (Number.isNaN(parsed)) return
  const current = which === 1 ? p1.value : p2.value
  const updated: Point2D = {
    x: axis === 'x' ? parsed : (current?.x ?? 0),
    y: axis === 'y' ? parsed : (current?.y ?? 0),
  }
  if (which === 1) {
    p1.value = updated
    activePoint.value = 1
  } else {
    p2.value = updated
    activePoint.value = 2
  }
  clickError.value = ''
  apiError.value = ''
}

function handleResetPoints() {
  if (isPanelDisabled.value || isSubmitting.value) return
  p1.value = null
  p2.value = null
  activePoint.value = 1
  clickError.value = ''
  apiError.value = ''
  attemptedSubmit.value = false
}

async function handleApplyCalibration() {
  if (isPanelDisabled.value || isSubmitting.value) return
  attemptedSubmit.value = true
  clickError.value = ''
  apiError.value = ''

  if (!validation.value.ok || !p1.value || !p2.value) {
    return
  }

  isSubmitting.value = true
  try {
    const updated = await putVisitCalibration(props.visit.id, {
      x1: p1.value.x,
      y1: p1.value.y,
      x2: p2.value.x,
      y2: p2.value.y,
      length_cm: Number(lengthCm.value),
    })
    emit('updated', updated)
    emit('notify', 'Kalibrasi dua titik berhasil diterapkan pada draf.')
  } catch (err) {
    if (err instanceof ApiError) {
      apiError.value = err.message
      if (err.status === 409) {
        isLocked409.value = true
        emit('conflict', err.message)
      }
    } else {
      apiError.value = 'Terjadi kesalahan saat menyimpan kalibrasi.'
    }
  } finally {
    isSubmitting.value = false
  }
}

async function handleDeleteCalibration() {
  if (isPanelDisabled.value || isSubmitting.value || !isApplied.value) return
  isSubmitting.value = true
  clickError.value = ''
  apiError.value = ''
  try {
    const updated = await deleteVisitCalibration(props.visit.id)
    p1.value = null
    p2.value = null
    lengthCm.value = 2
    attemptedSubmit.value = false
    emit('updated', updated)
    emit('notify', 'Kalibrasi dihapus. Pengukuran kembali memakai basis relatif (%).')
  } catch (err) {
    if (err instanceof ApiError) {
      apiError.value = err.message
      if (err.status === 409) {
        isLocked409.value = true
        emit('conflict', err.message)
      }
    } else {
      apiError.value = 'Terjadi kesalahan saat menghapus kalibrasi.'
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <details id="calbox" class="calbox" :open="isDetailsOpen" @toggle="onDetailsToggle">
    <summary>
      <span class="sum-l">Kalibrasi penggaris (opsional)</span>
      <span id="calChip" class="cal-chip" :class="{ on: isApplied }">
        {{
          isApplied && visit.area_cm2 !== null
            ? `Diterapkan · ${formatDecimalID(visit.area_cm2)} cm²`
            : 'Belum diterapkan'
        }}
      </span>
    </summary>

    <div class="cal-in">
      <ol>
        <li>
          Klik dua titik pada garis skala penggaris, sebaiknya garis angka yang jelas (misalnya 1
          ke 3 cm), bukan tepi penggaris.
        </li>
        <li>Isi panjang nyata antara kedua titik (cm), lalu tekan <b>Terapkan kalibrasi</b>.</li>
        <li>Penggaris harus dekat dan sebidang dengan permukaan luka.</li>
      </ol>

      <div
        class="cal-stage"
        tabindex="0"
        role="region"
        aria-label="Kanvas citra asli untuk memilih dua titik kalibrasi. Gunakan tombol panah untuk menggeser titik aktif, Shift untuk langkah 10 piksel."
        @keydown="onStageKeydown"
      >
        <img
          v-if="imageUrl"
          id="calImg"
          ref="imgRef"
          class="cal-img"
          :src="imageUrl"
          alt="Foto asli luka untuk penentuan dua titik kalibrasi penggaris"
          @click="handleImageClick"
          @load="measureBox"
        />
        <svg
          v-if="boxWidth > 0 && boxHeight > 0 && (dispP1 || dispP2)"
          class="cal-overlay"
          :viewBox="`0 0 ${boxWidth} ${boxHeight}`"
          aria-hidden="true"
        >
          <line
            v-if="dispP1 && dispP2"
            :x1="dispP1.x"
            :y1="dispP1.y"
            :x2="dispP2.x"
            :y2="dispP2.y"
            stroke="#0F2942"
            stroke-width="2.5"
            stroke-dasharray="6 4"
          />
          <g v-if="dispP1">
            <circle
              :cx="dispP1.x"
              :cy="dispP1.y"
              r="11"
              :fill="activePoint === 1 ? '#1F6368' : '#0F2942'"
              stroke="#FFFFFF"
              stroke-width="2.5"
            />
            <text
              :x="dispP1.x"
              :y="dispP1.y + 4"
              text-anchor="middle"
              fill="#FFFFFF"
              font-size="12"
              font-weight="700"
            >
              1
            </text>
          </g>
          <g v-if="dispP2">
            <circle
              :cx="dispP2.x"
              :cy="dispP2.y"
              r="11"
              :fill="activePoint === 2 ? '#1F6368' : '#0F2942'"
              stroke="#FFFFFF"
              stroke-width="2.5"
            />
            <text
              :x="dispP2.x"
              :y="dispP2.y + 4"
              text-anchor="middle"
              fill="#FFFFFF"
              font-size="12"
              font-weight="700"
            >
              2
            </text>
          </g>
        </svg>
      </div>

      <p class="cal-meta">
        Dimensi citra asli: <code>{{ imgWidthPx }} × {{ imgHeightPx }} px</code>
      </p>

      <p id="calStatus" class="cal-status" role="status" aria-live="polite">
        {{ statusText }}
      </p>

      <div class="cal-pts" role="group" aria-label="Pilih titik aktif dan alternatif papan ketik">
        <button
          id="pt1"
          type="button"
          class="btn btn-secondary"
          :aria-pressed="activePoint === 1"
          :disabled="isPanelDisabled || isSubmitting"
          @click="activePoint = 1"
        >
          {{ activePoint === 1 ? 'Titik 1 aktif' : 'Pilih Titik 1' }}
        </button>
        <button
          id="pt2"
          type="button"
          class="btn btn-secondary"
          :aria-pressed="activePoint === 2"
          :disabled="isPanelDisabled || isSubmitting"
          @click="activePoint = 2"
        >
          {{ activePoint === 2 ? 'Titik 2 aktif' : 'Pilih Titik 2' }}
        </button>
      </div>

      <div class="cal-coords-grid" aria-label="Koordinat piksel alternatif tanpa mouse">
        <div>
          <label for="calX1">X₁ (px)</label>
          <input
            id="calX1"
            type="number"
            step="0.1"
            :min="0"
            :max="imgWidthPx"
            :value="p1 ? p1.x : ''"
            :disabled="isPanelDisabled || isSubmitting"
            placeholder="0"
            @input="updatePointCoord(1, 'x', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div>
          <label for="calY1">Y₁ (px)</label>
          <input
            id="calY1"
            type="number"
            step="0.1"
            :min="0"
            :max="imgHeightPx"
            :value="p1 ? p1.y : ''"
            :disabled="isPanelDisabled || isSubmitting"
            placeholder="0"
            @input="updatePointCoord(1, 'y', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div>
          <label for="calX2">X₂ (px)</label>
          <input
            id="calX2"
            type="number"
            step="0.1"
            :min="0"
            :max="imgWidthPx"
            :value="p2 ? p2.x : ''"
            :disabled="isPanelDisabled || isSubmitting"
            placeholder="0"
            @input="updatePointCoord(2, 'x', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div>
          <label for="calY2">Y₂ (px)</label>
          <input
            id="calY2"
            type="number"
            step="0.1"
            :min="0"
            :max="imgHeightPx"
            :value="p2 ? p2.y : ''"
            :disabled="isPanelDisabled || isSubmitting"
            placeholder="0"
            @input="updatePointCoord(2, 'y', ($event.target as HTMLInputElement).value)"
          />
        </div>
      </div>

      <div class="cal-form">
        <div>
          <label for="calLen">Panjang fisik segmen (cm)</label>
          <input
            id="calLen"
            v-model.number="lengthCm"
            type="number"
            min="0.1"
            max="50"
            step="0.1"
            inputmode="decimal"
            :disabled="isPanelDisabled || isSubmitting"
          />
        </div>
        <dl class="cal-out" aria-live="polite">
          <div>
            <dt>Jarak titik (Δpx)</dt>
            <dd id="oDpx">
              {{ validation.deltaPx !== null ? `${formatDecimalID(validation.deltaPx, 1)} px` : '–' }}
            </dd>
          </div>
          <div>
            <dt>Skala s</dt>
            <dd id="oScale">
              {{
                isApplied && visit.scale_cm_per_px !== null
                  ? `${visit.scale_cm_per_px.toFixed(6).replace('.', ',')} cm/px`
                  : validation.scaleCmPerPx !== null
                    ? `${validation.scaleCmPerPx.toFixed(6).replace('.', ',')} cm/px`
                    : '–'
              }}
            </dd>
          </div>
          <div>
            <dt>Estimasi luas</dt>
            <dd id="oArea">
              {{
                isApplied && visit.area_cm2 !== null
                  ? `${formatDecimalID(visit.area_cm2)} cm²`
                  : validation.areaCm2 !== null
                    ? `${formatDecimalID(validation.areaCm2)} cm²`
                    : '–'
              }}
            </dd>
          </div>
        </dl>
      </div>

      <p v-if="visibleError" id="calErr" class="cal-err" role="alert">{{ visibleError }}</p>

      <div class="cal-act">
        <button
          id="calApply"
          class="btn btn-primary"
          type="button"
          :disabled="isPanelDisabled || isSubmitting"
          @click="handleApplyCalibration"
        >
          {{ isSubmitting ? 'Menyimpan kalibrasi...' : 'Terapkan kalibrasi' }}
        </button>
        <button
          id="calReset"
          class="btn btn-secondary"
          type="button"
          :disabled="isPanelDisabled || isSubmitting"
          @click="handleResetPoints"
        >
          Atur ulang titik
        </button>
        <button
          v-if="isApplied"
          id="calClear"
          class="btn btn-secondary"
          type="button"
          :disabled="isPanelDisabled || isSubmitting"
          @click="handleDeleteCalibration"
        >
          Hapus kalibrasi
        </button>
      </div>

      <p class="cal-limit">
        Kalibrasi mengoreksi perbedaan jarak kamera pada bidang penggaris. Kalibrasi tidak
        mengoreksi perbedaan sudut pandang 3D atau lengkungan permukaan anatomi, sehingga penggaris
        harus dekat dan sebidang dengan permukaan luka.
      </p>
    </div>
  </details>
</template>

<style scoped>
.calbox {
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}
.calbox summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 18px;
  min-height: 52px;
  font-size: 15px;
  font-weight: 650;
  color: var(--navy);
}
.calbox summary::-webkit-details-marker {
  display: none;
}
.calbox summary::before {
  content: '▸';
  margin-right: 8px;
  color: var(--teal);
  display: inline-block;
  transition: transform var(--dur);
}
.calbox[open] summary::before {
  transform: rotate(90deg);
}
.cal-chip {
  font-size: 12px;
  font-weight: 650;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  color: var(--text-2);
  background: var(--bg);
}
.cal-chip.on {
  color: var(--green);
  background: var(--green-bg);
  border-color: var(--green-bd);
}
.cal-in {
  padding: 4px 18px 18px;
  border-top: 1px solid var(--border);
}
.cal-in ol {
  margin: 14px 0 12px;
  padding-left: 20px;
  display: grid;
  gap: 4px;
  font-size: 13.5px;
  color: var(--text-2);
}
.cal-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: #e2e8f0;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  overflow: hidden;
}
.cal-stage:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}
.cal-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  cursor: crosshair;
  user-select: none;
}
.cal-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.cal-meta {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.cal-status {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-2);
}
.cal-pts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.cal-pts .btn[aria-pressed='true'] {
  background: var(--teal-soft);
  border-color: var(--teal);
  color: var(--navy);
}
.cal-coords-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.cal-coords-grid label,
.cal-form label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--navy);
  margin-bottom: 4px;
}
.cal-coords-grid input,
.cal-form input[type='number'] {
  height: 40px;
  width: 100%;
  padding: 0 10px;
  font: inherit;
  font-size: 14px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
}
.cal-form {
  display: grid;
  grid-template-columns: minmax(0, 200px) 1fr;
  gap: 12px 20px;
  margin-top: 14px;
  align-items: start;
}
.cal-out {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.cal-out div {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
}
.cal-out dt {
  font-size: 12px;
  color: var(--muted);
}
.cal-out dd {
  margin: 2px 0 0;
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 13.5px;
  color: var(--navy);
}
.cal-err {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--error);
  font-weight: 600;
}
.cal-act {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}
.cal-limit {
  margin: 14px 0 0;
  padding: 10px 12px;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-2);
  background: #f1f5f9;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 14px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
}
.btn:disabled {
  background: #e2e8f0;
  color: #475569;
  border-color: #cbd5e1;
  cursor: not-allowed;
}
.btn-primary {
  background: var(--navy);
  color: #fff;
}
.btn-secondary {
  background: var(--surface);
  color: var(--navy);
  border-color: var(--border-strong);
}

@media (max-width: 760px) {
  .cal-coords-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .cal-form,
  .cal-out {
    grid-template-columns: 1fr;
  }
}
</style>
