<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  hasFile: boolean
  isDemo: boolean
  isLoadingSample: boolean
  errorMessage: string
}

defineProps<Props>()

const emit = defineEmits<{
  'select-file': [file: File]
  'load-sample': []
}>()

const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const pickBtnRef = ref<HTMLButtonElement | null>(null)

function openPicker() {
  fileInputRef.value?.click()
}

function onDropzoneKeydown(e: KeyboardEvent) {
  if (e.target !== e.currentTarget) return
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    openPicker()
  }
}

function onFileInputChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('select-file', file)
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) emit('select-file', file)
}

function resetAndFocus() {
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
  pickBtnRef.value?.focus()
}

defineExpose({ resetAndFocus })
</script>

<template>
  <label id="foto-lbl" class="lbl" for="file">Foto Luka</label>

  <div
    v-if="!hasFile"
    id="drop"
    class="drop"
    :class="{ over: isDragging }"
    tabindex="0"
    role="button"
    aria-labelledby="foto-lbl drop-desc"
    @keydown="onDropzoneKeydown"
    @dragenter="onDragOver"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <svg
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <rect x="6" y="10" width="36" height="28" rx="4" />
      <circle cx="17" cy="20" r="3.5" />
      <path d="m6 33 10-9 8 7 7-6 11 9" />
      <path d="M36 4v8M32 8h8" />
    </svg>
    <p id="drop-desc">Seret foto ulkus ke area ini atau pilih dari perangkat</p>
    <div class="drop-actions">
      <button
        id="pick"
        ref="pickBtnRef"
        class="btn btn-secondary"
        type="button"
        @click.stop="openPicker"
      >
        Pilih Berkas Foto
      </button>
      <button
        v-if="isDemo"
        id="sample"
        class="btn btn-ghost"
        type="button"
        :disabled="isLoadingSample"
        @click.stop="emit('load-sample')"
      >
        {{ isLoadingSample ? 'Memuat Foto Sampel...' : 'Gunakan Foto Sampel (Mode demo)' }}
      </button>
    </div>
    <p class="hint" style="margin: 0">Format JPG atau PNG, maksimal 10 MB.</p>
  </div>

  <input
    id="file"
    ref="fileInputRef"
    type="file"
    accept="image/jpeg,image/png"
    class="sr"
    tabindex="-1"
    @change="onFileInputChange"
  />

  <p v-if="errorMessage" id="ferr" class="error" role="alert">{{ errorMessage }}</p>
</template>

<style scoped>
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.lbl {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
.hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 6px 0 0;
}
.drop {
  min-height: 220px;
  background: var(--bg);
  border: 1.5px dashed #64748b;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 10px;
  padding: 28px 20px;
  cursor: pointer;
  transition:
    border-color var(--dur),
    background-color var(--dur);
}
.drop:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
  border-color: var(--navy);
}
.drop.over {
  border-color: var(--teal);
  background: var(--teal-soft);
}
.drop svg {
  width: 44px;
  height: 44px;
  color: var(--teal);
}
.drop p {
  font-size: 14px;
  color: var(--text-2);
  max-width: 320px;
  margin: 0;
}
.drop-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 4px;
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
  margin-top: 10px;
  font-size: 13px;
  color: var(--error);
  font-weight: 500;
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
