<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ApiError, deleteVisitCalibration, putVisitCalibration } from '@/api/patients'
import type { VisitRecord } from '@/types/patient'
import {
  displayClickToOriginalPoint,
  getContainedImageRect,
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
const isDraggingPoint = ref(false)
let activePointerId: number | null = null
let dragPointWhich: 1 | 2 = 1
let wasP2EmptyOnDown = false

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
  () => syncFromVisit(props.visit),
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
    nextTick(() => requestAnimationFrame(measureBox))
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

const markerList = computed(() =>
  [
    dispP1.value ? { num: 1 as const, pt: dispP1.value } : null,
    dispP2.value ? { num: 2 as const, pt: dispP2.value } : null,
  ].filter((m): m is { num: 1 | 2; pt: NonNullable<typeof dispP1.value> } => m !== null),
)

const coordFields = computed(() => [
  { id: 'calX1', label: 'X₁ (px)', which: 1 as const, axis: 'x' as const, max: imgWidthPx.value, val: p1.value?.x ?? '' },
  { id: 'calY1', label: 'Y₁ (px)', which: 1 as const, axis: 'y' as const, max: imgHeightPx.value, val: p1.value?.y ?? '' },
  { id: 'calX2', label: 'X₂ (px)', which: 2 as const, axis: 'x' as const, max: imgWidthPx.value, val: p2.value?.x ?? '' },
  { id: 'calY2', label: 'Y₂ (px)', which: 2 as const, axis: 'y' as const, max: imgHeightPx.value, val: p2.value?.y ?? '' },
])

const visibleError = computed(() => {
  if (apiError.value) return apiError.value
  if (clickError.value) return clickError.value
  const len = Number(lengthCm.value)
  if (Number.isNaN(len) || len <= 0 || len > 50) {
    return 'Panjang penggaris nyata (length_cm) harus berada pada rentang (0, 50] cm.'
  }
  if ((p1.value !== null && p2.value !== null) || attemptedSubmit.value) {
    if (!validation.value.ok && validation.value.error) return validation.value.error
  }
  return ''
})

const statusText = computed(() => {
  if (isPanelDisabled.value) return 'Kalibrasi tidak dapat diubah karena kunjungan sudah tersimpan.'
  if (!p1.value) return 'Belum ada titik. Klik foto penggaris atau isi koordinat untuk menetapkan Titik 1.'
  if (!p2.value) return `Titik 1 di (${formatDecimalID(p1.value.x, 1)}, ${formatDecimalID(p1.value.y, 1)}) px. Klik foto untuk Titik 2.`
  if (!validation.value.ok) {
    return `Titik 1 (${formatDecimalID(p1.value.x, 1)}, ${formatDecimalID(p1.value.y, 1)}) & Titik 2 (${formatDecimalID(p2.value.x, 1)}, ${formatDecimalID(p2.value.y, 1)}) px — belum valid.`
  }
  return `Titik 1 (${formatDecimalID(p1.value.x, 1)}, ${formatDecimalID(p1.value.y, 1)}) & Titik 2 (${formatDecimalID(p2.value.x, 1)}, ${formatDecimalID(p2.value.y, 1)}) px siap diterapkan.`
})

const LOUPE_SIZE = 112
const LOUPE_ZOOM = 2.5

const loupeStyle = computed(() => {
  if (!isDraggingPoint.value || boxWidth.value <= 0 || boxHeight.value <= 0) return null
  const disp = dragPointWhich === 1 ? dispP1.value : dispP2.value
  if (!disp) return null

  const half = LOUPE_SIZE / 2
  const left = Math.max(8, Math.min(boxWidth.value - LOUPE_SIZE - 8, disp.x - half))
  const preferredTop = disp.y - LOUPE_SIZE - 44
  const top = preferredTop >= 8 ? preferredTop : Math.min(boxHeight.value - LOUPE_SIZE - 8, disp.y + 44)

  const contained = getContainedImageRect(
    boxWidth.value,
    boxHeight.value,
    imgWidthPx.value,
    imgHeightPx.value,
  )
  const renderW = contained.renderedWidth > 0 ? contained.renderedWidth : boxWidth.value
  const renderH = contained.renderedHeight > 0 ? contained.renderedHeight : boxHeight.value
  const localX = disp.x - contained.offsetX
  const localY = disp.y - contained.offsetY

  const bgW = renderW * LOUPE_ZOOM
  const bgH = renderH * LOUPE_ZOOM
  const bgX = half - localX * LOUPE_ZOOM
  const bgY = half - localY * LOUPE_ZOOM

  return {
    width: `${LOUPE_SIZE}px`,
    height: `${LOUPE_SIZE}px`,
    left: `${left}px`,
    top: `${top}px`,
    backgroundImage: `url("${props.imageUrl}")`,
    backgroundSize: `${bgW}px ${bgH}px`,
    backgroundPosition: `${bgX}px ${bgY}px`,
  }
})

function applyClientPoint(clientX: number, clientY: number, which: 1 | 2): boolean {
  if (!imgRef.value) return false
  const rect = imgRef.value.getBoundingClientRect()
  boxWidth.value = rect.width
  boxHeight.value = rect.height

  const conv = displayClickToOriginalPoint({
    clientX,
    clientY,
    boxRect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
    imgWidthPx: imgWidthPx.value,
    imgHeightPx: imgHeightPx.value,
  })

  apiError.value = ''
  if (!conv.ok || !conv.point) {
    clickError.value = 'Klik berada di luar foto. Klik tepat pada gambar penggaris.'
    return false
  }

  clickError.value = ''
  if (which === 1) {
    p1.value = conv.point
  } else {
    p2.value = conv.point
  }
  return true
}

function handlePointerDown(e: PointerEvent) {
  if (isPanelDisabled.value || isSubmitting.value || !imgRef.value) return
  if (e.pointerType === 'mouse' && e.button !== 0) return

  wasP2EmptyOnDown = p2.value === null
  if (!p1.value) {
    dragPointWhich = 1
    activePoint.value = 1
    attemptedSubmit.value = false
  } else if (!p2.value) {
    dragPointWhich = 2
    activePoint.value = 2
  } else {
    dragPointWhich = activePoint.value
  }

  if (!applyClientPoint(e.clientX, e.clientY, dragPointWhich)) return

  isDraggingPoint.value = true
  activePointerId = e.pointerId
  try {
    imgRef.value.setPointerCapture(e.pointerId)
  } catch {
    // Abaikan jika event sintetis tidak mendukung pointer capture
  }
}

function handlePointerMove(e: PointerEvent) {
  if (!isDraggingPoint.value) return
  if (activePointerId !== null && e.pointerId !== activePointerId) return
  applyClientPoint(e.clientX, e.clientY, dragPointWhich)
}

function handlePointerEnd(e: PointerEvent) {
  if (!isDraggingPoint.value) return
  isDraggingPoint.value = false
  if (imgRef.value && activePointerId !== null) {
    try {
      if (imgRef.value.hasPointerCapture(e.pointerId)) {
        imgRef.value.releasePointerCapture(e.pointerId)
      }
    } catch {
      // Abaikan jika pointer capture sudah lepas
    }
  }
  activePointerId = null
  if (dragPointWhich === 1 && wasP2EmptyOnDown && p1.value) {
    activePoint.value = 2
  }
}

function nudgeActivePoint(dx: number, dy: number) {
  if (isPanelDisabled.value || isSubmitting.value) return
  const targetPoint = activePoint.value === 1 ? p1.value : p2.value
  if (!targetPoint) return
  const nextPt = {
    x: Math.min(imgWidthPx.value, Math.max(0, Math.round((targetPoint.x + dx) * 10) / 10)),
    y: Math.min(imgHeightPx.value, Math.max(0, Math.round((targetPoint.y + dy) * 10) / 10)),
  }
  if (activePoint.value === 1) p1.value = nextPt
  else p2.value = nextPt
  clickError.value = ''
  apiError.value = ''
}

function onStageKeydown(e: KeyboardEvent) {
  if (isPanelDisabled.value || isSubmitting.value) return
  if (e.key === '1') { activePoint.value = 1; return }
  if (e.key === '2') { activePoint.value = 2; return }
  const targetPoint = activePoint.value === 1 ? p1.value : p2.value
  if (!targetPoint) return

  const step = e.shiftKey ? 10 : 1
  const deltas: Record<string, [number, number] | undefined> = {
    ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step],
  }
  const move = deltas[e.key]
  if (!move) return
  e.preventDefault()

  const nextPt = {
    x: Math.min(imgWidthPx.value, Math.max(0, targetPoint.x + move[0])),
    y: Math.min(imgHeightPx.value, Math.max(0, targetPoint.y + move[1])),
  }
  if (activePoint.value === 1) p1.value = nextPt
  else p2.value = nextPt
  clickError.value = ''
  apiError.value = ''
}

function updatePointCoord(which: 1 | 2, axis: 'x' | 'y', raw: string) {
  if (isPanelDisabled.value || isSubmitting.value || raw.trim() === '') return
  const parsed = Number(raw)
  if (Number.isNaN(parsed)) return
  const current = which === 1 ? p1.value : p2.value
  const updated: Point2D = {
    x: axis === 'x' ? parsed : (current?.x ?? 0),
    y: axis === 'y' ? parsed : (current?.y ?? 0),
  }
  if (which === 1) { p1.value = updated; activePoint.value = 1 }
  else { p2.value = updated; activePoint.value = 2 }
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
  if (!validation.value.ok || !p1.value || !p2.value) return

  isSubmitting.value = true
  try {
    const updated = await putVisitCalibration(props.visit.id, {
      x1: p1.value.x, y1: p1.value.y, x2: p2.value.x, y2: p2.value.y, length_cm: Number(lengthCm.value),
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
    emit('notify', 'Kalibrasi dihapus. Pengukuran kembali memakai luas foto.')
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
            ? `Diterapkan · ${formatDecimalID(visit.area_cm2, 1)} cm²`
            : 'Belum diterapkan'
        }}
      </span>
    </summary>

    <div class="cal-in">
      <ol>
        <li>
          Sentuh atau seret pada foto untuk menandai <b>2 garis angka</b> di penggaris (bukan tepi penggaris).
        </li>
        <li>Pilih jarak kedua titik (cm), lalu tekan <b>Terapkan kalibrasi</b>.</li>
        <li>Pastikan penggaris dekat dan sejajar dengan permukaan luka.</li>
      </ol>

      <div
        class="cal-stage"
        tabindex="0"
        role="region"
        aria-label="Foto asli untuk memilih dua titik kalibrasi. Gunakan tombol panah untuk menggeser titik aktif, Shift untuk langkah 10 piksel."
        @keydown="onStageKeydown"
      >
        <img
          v-if="imageUrl"
          id="calImg"
          ref="imgRef"
          class="cal-img"
          :class="{ 'cal-img-interactive': !isPanelDisabled && !isSubmitting }"
          :src="imageUrl"
          alt="Foto asli luka untuk penentuan dua titik kalibrasi penggaris"
          draggable="false"
          @pointerdown="handlePointerDown"
          @pointermove="handlePointerMove"
          @pointerup="handlePointerEnd"
          @pointercancel="handlePointerEnd"
          @load="measureBox"
        />
        <div
          v-if="loupeStyle"
          class="cal-loupe"
          :style="loupeStyle"
          aria-hidden="true"
        >
          <span class="cal-loupe-cross-h"></span>
          <span class="cal-loupe-cross-v"></span>
          <span class="cal-loupe-dot"></span>
        </div>
        <svg
          v-if="boxWidth > 0 && boxHeight > 0 && markerList.length"
          class="cal-overlay"
          :viewBox="`0 0 ${boxWidth} ${boxHeight}`"
          aria-hidden="true"
        >
          <line
            v-if="dispP1 && dispP2"
            :x1="dispP1.x" :y1="dispP1.y" :x2="dispP2.x" :y2="dispP2.y"
            stroke="#0F2942" stroke-width="2.5" stroke-dasharray="6 4"
          />
          <g v-for="m in markerList" :key="m.num">
            <circle
              :cx="m.pt.x" :cy="m.pt.y" r="11"
              :fill="activePoint === m.num ? '#1F6368' : '#0F2942'"
              stroke="#FFFFFF" stroke-width="2.5"
            />
            <text
              :x="m.pt.x" :y="m.pt.y + 4" text-anchor="middle"
              fill="#FFFFFF" font-size="12" font-weight="700"
            >{{ m.num }}</text>
          </g>
        </svg>
      </div>

      <p id="calStatus" class="cal-status" role="status" aria-live="polite">{{ statusText }}</p>

      <div class="cal-pts" role="group" aria-label="Pilih titik aktif dan geser halus">
        <button
          id="pt1" type="button" class="btn btn-secondary"
          :aria-pressed="activePoint === 1" :disabled="isPanelDisabled || isSubmitting"
          @click="activePoint = 1"
        >{{ activePoint === 1 ? 'Titik 1 aktif' : 'Pilih Titik 1' }}</button>
        <button
          id="pt2" type="button" class="btn btn-secondary"
          :aria-pressed="activePoint === 2" :disabled="isPanelDisabled || isSubmitting"
          @click="activePoint = 2"
        >{{ activePoint === 2 ? 'Titik 2 aktif' : 'Pilih Titik 2' }}</button>

        <div class="cal-nudge" role="group" aria-label="Geser halus titik aktif 1 piksel">
          <button
            type="button" class="btn btn-secondary cal-nudge-btn"
            aria-label="Geser titik aktif ke kiri 1 piksel"
            :disabled="isPanelDisabled || isSubmitting || !(activePoint === 1 ? p1 : p2)"
            @click="nudgeActivePoint(-1, 0)"
          >←</button>
          <button
            type="button" class="btn btn-secondary cal-nudge-btn"
            aria-label="Geser titik aktif ke atas 1 piksel"
            :disabled="isPanelDisabled || isSubmitting || !(activePoint === 1 ? p1 : p2)"
            @click="nudgeActivePoint(0, -1)"
          >↑</button>
          <button
            type="button" class="btn btn-secondary cal-nudge-btn"
            aria-label="Geser titik aktif ke bawah 1 piksel"
            :disabled="isPanelDisabled || isSubmitting || !(activePoint === 1 ? p1 : p2)"
            @click="nudgeActivePoint(0, 1)"
          >↓</button>
          <button
            type="button" class="btn btn-secondary cal-nudge-btn"
            aria-label="Geser titik aktif ke kanan 1 piksel"
            :disabled="isPanelDisabled || isSubmitting || !(activePoint === 1 ? p1 : p2)"
            @click="nudgeActivePoint(1, 0)"
          >→</button>
        </div>
      </div>

      <div class="cal-form">
        <div class="cal-len-group">
          <label for="calLen">Jarak dua titik di penggaris (cm)</label>
          <div class="cal-presets" role="group" aria-label="Pilih cepat jarak penggaris">
            <button
              v-for="preset in [1, 2, 3, 5]"
              :key="preset"
              type="button"
              class="btn btn-secondary cal-preset-btn"
              :aria-pressed="lengthCm === preset"
              :disabled="isPanelDisabled || isSubmitting"
              @click="lengthCm = preset"
            >{{ preset }} cm</button>
          </div>
          <input
            id="calLen" v-model.number="lengthCm" type="number"
            min="0.1" max="50" step="0.1" inputmode="decimal"
            :disabled="isPanelDisabled || isSubmitting"
          />
        </div>
        <dl class="cal-out" aria-live="polite">
          <div class="cal-area-card">
            <dt>{{ isApplied ? 'Luas luka terkalibrasi' : 'Perkiraan luas luka' }}</dt>
            <dd id="oArea">
              {{
                isApplied && visit.area_cm2 !== null
                  ? `${formatDecimalID(visit.area_cm2, 1)} cm²`
                  : validation.areaCm2 !== null
                    ? `${formatDecimalID(validation.areaCm2, 1)} cm²`
                    : '–'
              }}
            </dd>
          </div>
        </dl>
      </div>

      <p v-if="visibleError" id="calErr" class="cal-err" role="alert">{{ visibleError }}</p>

      <div class="cal-act">
        <button
          id="calApply" class="btn btn-primary" type="button"
          :disabled="isPanelDisabled || isSubmitting" @click="handleApplyCalibration"
        >{{ isSubmitting ? 'Menyimpan kalibrasi...' : 'Terapkan kalibrasi' }}</button>
        <button
          id="calReset" class="btn btn-secondary" type="button"
          :disabled="isPanelDisabled || isSubmitting" @click="handleResetPoints"
        >Atur ulang titik</button>
        <button
          v-if="isApplied" id="calClear" class="btn btn-secondary" type="button"
          :disabled="isPanelDisabled || isSubmitting" @click="handleDeleteCalibration"
        >Hapus kalibrasi</button>
      </div>

      <details class="cal-tech">
        <summary>Atur koordinat &amp; detail teknis</summary>
        <div class="cal-tech-body">
          <p class="cal-meta">Ukuran foto asli: <code>{{ imgWidthPx }} × {{ imgHeightPx }} px</code></p>

          <div class="cal-coords-grid" aria-label="Koordinat piksel alternatif tanpa mouse">
            <div v-for="f in coordFields" :key="f.id">
              <label :for="f.id">{{ f.label }}</label>
              <input
                :id="f.id" type="number" step="any" :min="0" :max="f.max"
                :value="f.val" :disabled="isPanelDisabled || isSubmitting" placeholder="0"
                @input="updatePointCoord(f.which, f.axis, ($event.target as HTMLInputElement).value)"
              />
            </div>
          </div>

          <dl class="cal-out cal-out-tech" aria-live="polite">
            <div>
              <dt>Jarak titik (Δpx)</dt>
              <dd id="oDpx">{{ validation.deltaPx !== null ? `${formatDecimalID(validation.deltaPx, 1)} px` : '–' }}</dd>
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
          </dl>

          <p class="cal-limit">
            Kalibrasi mengoreksi perbedaan jarak kamera pada bidang penggaris. Kalibrasi tidak
            mengoreksi perbedaan sudut pandang 3D atau lengkungan permukaan anatomi, sehingga penggaris
            harus dekat dan sebidang dengan permukaan luka.
          </p>
        </div>
      </details>
    </div>
  </details>
</template>

<style scoped src="../assets/h4_calibration.css"></style>
