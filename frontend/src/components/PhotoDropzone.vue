<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { COARSE_POINTER_QUERY, isCoarsePointerDevice } from '@/utils/touchDevice';

defineProps<{
  error?: string;
  showSampleButton?: boolean;
}>();

const emit = defineEmits<{
  (e: 'select', file: File): void;
  (e: 'sample'): void;
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);
const cameraInputRef = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);
const isTouchDevice = ref(isCoarsePointerDevice());

let mediaQueryList: MediaQueryList | null = null;

function updatePointerMode(matches: boolean) {
  isTouchDevice.value = matches;
}

function handleMediaChange(event: MediaQueryListEvent) {
  updatePointerMode(event.matches);
}

onMounted(() => {
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    mediaQueryList = window.matchMedia(COARSE_POINTER_QUERY);
    updatePointerMode(mediaQueryList.matches);
    mediaQueryList.addEventListener('change', handleMediaChange);
  }
});

onBeforeUnmount(() => {
  mediaQueryList?.removeEventListener('change', handleMediaChange);
  mediaQueryList = null;
});

// Tahap 2 akan mengganti isi onTakePhoto() untuk membuka kamera langsung (getUserMedia + bayangan foto awal).
function onTakePhoto() {
  cameraInputRef.value?.click();
}

function openPicker() {
  fileInputRef.value?.click();
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (file) {
    emit('select', file);
  }
  target.value = '';
}

function handleDragOver(event: DragEvent) {
  if (isTouchDevice.value) return;
  event.preventDefault();
  isDragging.value = true;
}

function handleDragLeave() {
  isDragging.value = false;
}

function handleDrop(event: DragEvent) {
  if (isTouchDevice.value) return;
  event.preventDefault();
  isDragging.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    emit('select', file);
  }
}
</script>

<template>
  <div class="drop-wrap">
    <div
      id="drop"
      class="drop"
      :class="{ dragging: isDragging }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <input
        id="file-camera"
        ref="cameraInputRef"
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        class="sr-only"
        @change="handleFileChange"
      />
      <input
        id="file"
        ref="fileInputRef"
        type="file"
        accept="image/jpeg,image/png"
        class="sr-only"
        @change="handleFileChange"
      />

      <p class="drop-title">
        {{
          isTouchDevice
            ? 'Ambil foto luka atau pilih dari galeri.'
            : 'Seret foto luka ke sini atau pilih dari perangkat'
        }}
      </p>

      <div class="drop-actions">
        <button
          v-if="isTouchDevice"
          id="take-photo"
          type="button"
          class="btn btn-primary"
          @click="onTakePhoto"
        >
          Ambil Foto
        </button>

        <button id="pick" type="button" class="btn btn-secondary" @click="openPicker">
          {{ isTouchDevice ? 'Dari galeri' : 'Pilih Foto' }}
        </button>

        <button
          v-if="showSampleButton"
          id="sample"
          type="button"
          class="btn btn-ghost"
          @click="emit('sample')"
        >
          Pakai foto sampel (mode demo)
        </button>
      </div>

      <p class="drop-hint">JPG atau PNG, maksimal 10 MB.</p>
    </div>
    <p v-if="error" id="ferr" class="error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.drop-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.drop {
  flex: 1;
  min-height: 200px;
  border: 2px dashed var(--border-strong);
  border-radius: 8px;
  background: var(--bg);
  padding: 20px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 14px;
  transition:
    background-color var(--dur),
    border-color var(--dur);
}
.drop.dragging {
  border-color: var(--teal);
  background: var(--teal-soft);
}
.drop-title {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
  color: var(--navy);
  max-width: 280px;
}
.drop-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px 12px;
  width: 100%;
}
.drop-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 44px;
  min-width: 44px;
  padding: 0 18px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  border-radius: var(--radius);
  border: 1px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color var(--dur),
    border-color var(--dur);
}
.btn:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.btn-primary {
  background: var(--navy);
  color: #fff;
}
.btn-primary:hover:not(:disabled) {
  background: var(--navy-hover);
}
.btn-secondary {
  background: var(--surface);
  color: var(--navy);
  border-color: var(--border-strong);
}
.btn-secondary:hover:not(:disabled) {
  border-color: var(--navy);
  background: var(--bg);
}
.btn-ghost {
  background: none;
  color: var(--teal);
  padding: 0 10px;
}
.btn-ghost:hover {
  text-decoration: underline;
}
.error {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--error);
  font-weight: 500;
}
@media (min-width: 760px) {
  .drop {
    height: clamp(240px, 42vh, 380px);
  }
}
@media (max-width: 640px) {
  .drop-actions .btn {
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .drop,
  .btn {
    transition: none;
  }
}
</style>
