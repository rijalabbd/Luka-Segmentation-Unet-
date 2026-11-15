<script setup lang="ts">
import { computed, ref } from 'vue';
import { clampGhostPosition, clampGhostScale } from '@/utils/ghostTransform';

const props = defineProps<{
  previewUrl: string;
  fileName: string;
  fileSizeText: string;
  refImageUrl: string | null;
  ghostActive: boolean;
  ghostOpacity: number;
  ghostScale: number;
  ghostX: number;
  ghostY: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: 'replace'): void;
  (e: 'update:ghostX', value: number): void;
  (e: 'update:ghostY', value: number): void;
  (e: 'update:ghostScale', value: number): void;
}>();

const stackRef = ref<HTMLElement | null>(null);
const isDragging = ref(false);
let activePointerId: number | null = null;
let dragStartClientX = 0;
let dragStartClientY = 0;
let dragStartGhostX = 0;
let dragStartGhostY = 0;

const isInteractive = computed(() => props.ghostActive && Boolean(props.refImageUrl));

const ghostStyle = computed(() => ({
  opacity: props.ghostOpacity / 100,
  transform: `translate(${props.ghostX}px, ${props.ghostY}px) scale(${props.ghostScale / 100})`,
  transformOrigin: 'center',
}));

function handlePointerDown(event: PointerEvent) {
  if (!isInteractive.value || !stackRef.value) return;
  if (event.button !== 0 && event.pointerType === 'mouse') return;
  isDragging.value = true;
  activePointerId = event.pointerId;
  dragStartClientX = event.clientX;
  dragStartClientY = event.clientY;
  dragStartGhostX = props.ghostX;
  dragStartGhostY = props.ghostY;
  try {
    stackRef.value.setPointerCapture(event.pointerId);
  } catch {
    // Ignore if synthetic event has no active pointer
  }
}

function handlePointerMove(event: PointerEvent) {
  if (!isDragging.value || !stackRef.value) return;
  if (activePointerId !== null && event.pointerId !== activePointerId) return;
  const rect = stackRef.value.getBoundingClientRect();
  const dx = event.clientX - dragStartClientX;
  const dy = event.clientY - dragStartClientY;
  const clamped = clampGhostPosition(
    dragStartGhostX + dx,
    dragStartGhostY + dy,
    rect.width,
    rect.height,
  );
  emit('update:ghostX', clamped.x);
  emit('update:ghostY', clamped.y);
}

function handlePointerEnd(event: PointerEvent) {
  if (!isDragging.value) return;
  isDragging.value = false;
  if (stackRef.value && activePointerId !== null) {
    try {
      if (stackRef.value.hasPointerCapture(event.pointerId)) {
        stackRef.value.releasePointerCapture(event.pointerId);
      }
    } catch {
      // Ignore synthetic pointer capture release errors
    }
  }
  activePointerId = null;
}

function handleKeydown(event: KeyboardEvent) {
  if (!isInteractive.value || !stackRef.value) return;
  const step = event.shiftKey ? 10 : 2;
  const rect = stackRef.value.getBoundingClientRect();

  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    const clamped = clampGhostPosition(props.ghostX - step, props.ghostY, rect.width, rect.height);
    emit('update:ghostX', clamped.x);
  } else if (event.key === 'ArrowRight') {
    event.preventDefault();
    const clamped = clampGhostPosition(props.ghostX + step, props.ghostY, rect.width, rect.height);
    emit('update:ghostX', clamped.x);
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    const clamped = clampGhostPosition(props.ghostX, props.ghostY - step, rect.width, rect.height);
    emit('update:ghostY', clamped.y);
  } else if (event.key === 'ArrowDown') {
    event.preventDefault();
    const clamped = clampGhostPosition(props.ghostX, props.ghostY + step, rect.width, rect.height);
    emit('update:ghostY', clamped.y);
  } else if (event.key === '+' || event.key === '=') {
    event.preventDefault();
    emit('update:ghostScale', clampGhostScale(props.ghostScale + 1));
  } else if (event.key === '-' || event.key === '_') {
    event.preventDefault();
    emit('update:ghostScale', clampGhostScale(props.ghostScale - 1));
  }
}
</script>

<template>
  <div id="preview" class="preview-wrap">
    <div
      id="stack"
      ref="stackRef"
      class="frame"
      :class="{ 'ghost-interactive': isInteractive, 'ghost-dragging': isDragging }"
      :tabindex="isInteractive ? 0 : undefined"
      :role="isInteractive ? 'group' : undefined"
      :aria-label="isInteractive ? 'Geser foto awal' : undefined"
      @pointerdown="handlePointerDown"
      @pointermove="handlePointerMove"
      @pointerup="handlePointerEnd"
      @pointercancel="handlePointerEnd"
      @keydown="handleKeydown"
    >
      <img id="img" :src="previewUrl" alt="Pratinjau foto luka yang dipilih" draggable="false" />
      <img
        v-if="ghostActive && refImageUrl"
        id="ghost"
        :src="refImageUrl"
        alt=""
        aria-hidden="true"
        class="ghost-img"
        draggable="false"
        :style="ghostStyle"
      />
    </div>

    <div class="fileinfo">
      <div class="file-meta">
        <span id="fname" class="fname">{{ fileName }}</span>
        <span id="fsize" class="fsize">{{ fileSizeText }}</span>
      </div>
      <div class="fileinfo-actions">
        <span class="fcheck">✓ Foto siap</span>
        <button
          id="replace"
          type="button"
          class="btn btn-sm"
          :disabled="disabled"
          @click="emit('replace')"
        >
          Ganti Foto
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.frame {
  position: relative;
  width: 100%;
  height: 200px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
  user-select: none;
}
@media (min-width: 760px) {
  .frame {
    height: clamp(240px, 42vh, 380px);
  }
}
.frame.ghost-interactive {
  cursor: grab;
  touch-action: none;
}
.frame.ghost-dragging {
  cursor: grabbing;
}
.frame.ghost-interactive:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.frame img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.ghost-img {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.fileinfo {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px 12px;
  flex-wrap: wrap;
}
.file-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.fname {
  font-size: 13px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fsize {
  font-size: 12.5px;
  color: var(--text-muted);
  flex: none;
}
.fileinfo-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
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
  min-height: 36px;
  padding: 0 12px;
  font: inherit;
  font-size: 13px;
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
.btn:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
