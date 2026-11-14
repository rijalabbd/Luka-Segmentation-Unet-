<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { PatientSummary, VisitRecord } from '@/types/patient'
import { formatDateID, formatDecimalID } from '@/utils/formatters'

interface Props {
  patient: PatientSummary
  visitToDelete: VisitRecord | null
  previousVisit: VisitRecord | null
  visitCount: number
  showPatientModal: boolean
  isDeletingVisit: boolean
  isDeletingPatient: boolean
  visitError: string
  patientError: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  confirmDeleteVisit: []
  confirmDeletePatient: []
}>()

const visitModalRef = ref<HTMLDivElement | null>(null)
const patientModalRef = ref<HTMLDivElement | null>(null)
const visitCancelBtnRef = ref<HTMLButtonElement | null>(null)
const confirmRmInputRef = ref<HTMLInputElement | null>(null)
const confirmRmText = ref('')

const isRmMatch = computed(
  () => confirmRmText.value.trim().toUpperCase() === props.patient.id.toUpperCase(),
)

const confirmHint = computed(() => {
  const trimmed = confirmRmText.value.trim()
  if (!trimmed) {
    return 'Tombol hapus aktif setelah nomor rekam medis diketik dengan benar.'
  }
  if (isRmMatch.value) {
    return 'Nomor RM sesuai. Tombol hapus kini aktif.'
  }
  return `Nomor RM belum sesuai. Ketik ${props.patient.id} persis seperti tertera.`
})

const visitDescription = computed(() => {
  const v = props.visitToDelete
  if (!v) return ''
  const vNum = v.visit_index ?? props.visitCount
  const area =
    v.measure_mode === 'calibrated' && v.area_cm2 !== null
      ? `${formatDecimalID(v.area_cm2)} cm²`
      : `${formatDecimalID(v.area_pct)}%`
  const nameLabel = props.patient.nama
    ? `${props.patient.nama} (${props.patient.id})`
    : props.patient.id
  return (
    `Anda akan menghapus data Kunjungan ke-${vNum} (${formatDateID(v.visit_date)}) untuk pasien ` +
    `${nameLabel}. Data luas luka ${area} dan hasil segmentasinya akan dihapus permanen dari rekam aktif.`
  )
})

const lifoNote = computed(() => {
  if (props.previousVisit) {
    const prevNum = props.previousVisit.visit_index ?? Math.max(1, props.visitCount - 1)
    return `Sesuai aturan LIFO, rekam Kunjungan ke-${prevNum} akan kembali menjadi data aktif terkini.`
  }
  return 'Sesuai aturan LIFO, penghapusan baseline (Kunjungan ke-1) akan mengosongkan riwayat kunjungan pasien ini.'
})

function handleDialogKeydown(e: KeyboardEvent, container: HTMLDivElement | null) {
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
    return
  }
  if (e.key !== 'Tab' || !container) return
  const focusables = Array.from(
    container.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), [href], select:not(:disabled)',
    ),
  )
  if (focusables.length === 0) return
  const idx = focusables.indexOf(document.activeElement as HTMLElement)
  if (e.shiftKey && idx <= 0) {
    e.preventDefault()
    focusables[focusables.length - 1]?.focus()
  } else if (!e.shiftKey && idx === focusables.length - 1) {
    e.preventDefault()
    focusables[0]?.focus()
  }
}

watch(
  () => props.visitToDelete,
  (val) => {
    if (val) {
      nextTick(() => visitCancelBtnRef.value?.focus())
    }
  },
)

watch(
  () => props.showPatientModal,
  (open) => {
    if (open) {
      confirmRmText.value = ''
      nextTick(() => confirmRmInputRef.value?.focus())
    }
  },
)
</script>

<template>
  <div
    v-if="visitToDelete"
    id="mVisit"
    class="modal-back"
    @click.self="emit('close')"
    @keydown="handleDialogKeydown($event, visitModalRef)"
  >
    <div
      ref="visitModalRef"
      class="modal"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="mv-t"
      aria-describedby="mv-d"
    >
      <h2 id="mv-t">Hapus Data Kunjungan Terakhir?</h2>
      <p id="mv-d">{{ visitDescription }}</p>
      <p id="mv-log" class="log-note">{{ lifoNote }}</p>
      <p v-if="visitError" id="visitDeleteErr" class="err" role="alert">{{ visitError }}</p>
      <div class="btns">
        <button
          ref="visitCancelBtnRef"
          class="btn btn-secondary"
          type="button"
          :disabled="isDeletingVisit"
          @click="emit('close')"
        >
          Batal
        </button>
        <button
          id="doDeleteVisit"
          class="btn btn-danger"
          type="button"
          :disabled="isDeletingVisit"
          @click="emit('confirmDeleteVisit')"
        >
          {{ isDeletingVisit ? 'Menghapus...' : 'Hapus Kunjungan' }}
        </button>
      </div>
    </div>
  </div>

  <div
    v-if="showPatientModal"
    id="mPatient"
    class="modal-back"
    @click.self="emit('close')"
    @keydown="handleDialogKeydown($event, patientModalRef)"
  >
    <div
      ref="patientModalRef"
      class="modal"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="mp-t"
      aria-describedby="mp-d"
    >
      <h2 id="mp-t">Hapus Seluruh Rekam Pasien {{ patient.id }}?</h2>
      <p id="mp-d">
        Tindakan ini akan menghapus identitas {{ patient.nama || patient.id }} ({{ patient.id }})
        beserta seluruh {{ visitCount }} riwayat kunjungan, citra luka, hasil segmentasi masker,
        dan analisis longitudinal secara permanen.
      </p>
      <p class="warn-box">
        Tindakan ini permanen dan tidak dapat dibatalkan setelah dikonfirmasi.
      </p>

      <div class="field">
        <label for="confirmRM">
          Ketik <b class="mono">{{ patient.id }}</b> untuk mengonfirmasi
        </label>
        <input
          id="confirmRM"
          ref="confirmRmInputRef"
          v-model="confirmRmText"
          class="control mono"
          type="text"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
          :placeholder="patient.id"
          :disabled="isDeletingPatient"
          :aria-invalid="Boolean(confirmRmText.trim() && !isRmMatch)"
          aria-describedby="confirm-hint"
          @keydown.enter="isRmMatch && !isDeletingPatient && emit('confirmDeletePatient')"
        />
        <p id="confirm-hint" class="hint" role="status" aria-live="polite">{{ confirmHint }}</p>
      </div>

      <p v-if="patientError" id="patientDeleteErr" class="err" role="alert">{{ patientError }}</p>

      <div class="btns">
        <button
          class="btn btn-secondary"
          type="button"
          :disabled="isDeletingPatient"
          @click="emit('close')"
        >
          Batal
        </button>
        <button
          id="doDeletePatient"
          class="btn btn-danger"
          type="button"
          :disabled="!isRmMatch || isDeletingPatient"
          @click="emit('confirmDeletePatient')"
        >
          {{ isDeletingPatient ? 'Menghapus Pasien...' : 'Hapus Pasien Permanen' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-back {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: grid; place-items: center; padding: 16px; z-index: 50; overflow: auto;
}
.modal {
  background: #fff; border-radius: 10px; max-width: 480px; width: 100%;
  padding: 24px 24px 20px; box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}
.modal h2 { margin: 0 0 8px; font-size: 18px; color: var(--navy); }
.modal p { margin: 0; font-size: 14px; color: var(--text-2); line-height: 1.6; }
.log-note {
  margin-top: 14px !important; padding: 10px 12px; font-size: 13px !important;
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
}
.warn-box {
  margin-top: 14px !important; padding: 12px 14px; font-size: 13px !important;
  background: var(--error-bg); border: 1px solid #fca5a5; border-radius: 8px; color: var(--text) !important;
}
.field { margin-top: 16px; }
.field label { display: block; font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 6px; }
.mono { font-family: var(--mono); letter-spacing: 0.02em; }
.control {
  width: 100%; height: 44px; padding: 0 12px; font: inherit; font-size: 14px;
  color: var(--text); background: #fff; border: 1px solid var(--border-strong); border-radius: 6px;
}
.control:focus { outline: none; border-color: var(--navy); box-shadow: 0 0 0 2px var(--navy); }
.control[aria-invalid='true'] { border-color: var(--error); }
.hint { margin: 6px 0 0 !important; font-size: 13px !important; color: var(--text-2) !important; }
.err { margin: 10px 0 0 !important; font-size: 13px !important; color: var(--error) !important; font-weight: 600; }
.btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; flex-wrap: wrap; }
.btn {
  display: inline-flex; align-items: center; justify-content: center; min-height: 44px;
  padding: 0 18px; font: inherit; font-size: 14px; font-weight: 600; border-radius: 6px;
  border: 1px solid transparent; cursor: pointer;
}
.btn-secondary { background: var(--surface); color: var(--navy); border-color: var(--border-strong); }
.btn-secondary:hover:not(:disabled) { border-color: var(--navy); background: var(--bg); }
.btn-danger { background: var(--error); color: #fff; }
.btn-danger:hover:not(:disabled) { background: #991b1b; }
.btn-danger:disabled, .btn-secondary:disabled {
  background: #e2e8f0; color: #475569; border-color: #cbd5e1; cursor: not-allowed;
}
@media (max-width: 767px) {
  .btns { flex-direction: column-reverse; }
  .btns .btn { width: 100%; }
}
</style>
