<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

interface Props {
  showSave: boolean
  showDiscard: boolean
  saveDescription: string
  visitNumber: number
  isConfirming: boolean
  isDiscarding: boolean
  saveError: string
  discardError: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  confirmSave: []
  confirmDiscard: []
}>()

const saveConfirmRef = ref<HTMLButtonElement | null>(null)
const discardCancelRef = ref<HTMLButtonElement | null>(null)

watch(
  () => props.showSave,
  (open) => {
    if (open) nextTick(() => saveConfirmRef.value?.focus())
  },
)

watch(
  () => props.showDiscard,
  (open) => {
    if (open) nextTick(() => discardCancelRef.value?.focus())
  },
)
</script>

<template>
  <div
    v-if="showSave"
    id="mSave"
    class="modal-back"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div
      class="modal"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="ms-t"
      aria-describedby="ms-d"
    >
      <h2 id="ms-t">Simpan hasil pemeriksaan?</h2>
      <p id="ms-d">{{ saveDescription }}</p>
      <p v-if="saveError" id="saveErr" class="err" role="alert">{{ saveError }}</p>
      <div class="btns">
        <button class="btn btn-secondary" type="button" :disabled="isConfirming" @click="emit('close')">
          Batal
        </button>
        <button
          id="doSave"
          ref="saveConfirmRef"
          class="btn btn-primary"
          type="button"
          :disabled="isConfirming"
          @click="emit('confirmSave')"
        >
          {{ isConfirming ? 'Menyimpan...' : 'Konfirmasi dan Simpan' }}
        </button>
      </div>
    </div>
  </div>

  <div
    v-if="showDiscard"
    id="mDiscard"
    class="modal-back"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div
      class="modal"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="md-t"
      aria-describedby="md-d"
    >
      <h2 id="md-t">Foto ulang pemeriksaan?</h2>
      <p id="md-d">
        Pemeriksaan ke-{{ visitNumber }} belum tersimpan dan akan dihapus, termasuk kalibrasi
        penggaris jika ada. Anda akan kembali ke halaman Unggah Foto.
      </p>
      <p v-if="discardError" class="err" role="alert">{{ discardError }}</p>
      <div class="btns">
        <button
          ref="discardCancelRef"
          class="btn btn-secondary"
          type="button"
          :disabled="isDiscarding"
          @click="emit('close')"
        >
          Batal
        </button>
        <button
          id="doDiscard"
          class="btn btn-danger"
          type="button"
          :disabled="isDiscarding"
          @click="emit('confirmDiscard')"
        >
          {{ isDiscarding ? 'Menghapus...' : 'Hapus dan Foto Ulang' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-back { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.5); display: grid; place-items: center; padding: 16px; z-index: 50; }
.modal { background: #fff; border-radius: 10px; max-width: 480px; width: 100%; padding: 24px 24px 20px; box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25); }
.modal h2 { margin: 0 0 8px; font-size: 18px; color: var(--navy); }
.modal p { margin: 0; font-size: 14px; color: var(--text-2); line-height: 1.6; }
.modal .btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; flex-wrap: wrap; }
.err { margin-top: 10px; font-size: 14px; color: var(--error); font-weight: 500; }
.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 0 18px; font: inherit; font-size: 14px; font-weight: 600; border-radius: 6px; border: 1px solid transparent; cursor: pointer; }
.btn:disabled { background: #e2e8f0; color: #475569; border-color: #cbd5e1; cursor: not-allowed; }
.btn-primary { background: var(--navy); color: #fff; }
.btn-secondary { background: var(--surface); color: var(--navy); border-color: var(--border-strong); }
.btn-danger { background: var(--error); color: #fff; }
@media (max-width: 760px) { .modal .btns { flex-direction: column-reverse; } .modal .btns .btn { width: 100%; } }
</style>
