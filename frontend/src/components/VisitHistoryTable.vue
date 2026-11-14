<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { VisitRecord } from '@/types/patient'
import { formatDateID, formatDecimalID, formatSignedDecimalID } from '@/utils/formatters'
import { buildActiveWarnings, getTrendCssClass, type WarningMeta } from '@/utils/visitWarnings'

interface Props {
  visits: VisitRecord[]
  allowDelete?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  allowDelete: false,
})

const emit = defineEmits<{
  requestDelete: [visit: VisitRecord]
}>()

function visitNumber(v: VisitRecord, idx: number): number {
  return v.visit_index ?? idx + 1
}

function areaText(v: VisitRecord): string {
  if (v.measure_mode === 'calibrated' && v.area_cm2 !== null) {
    return `${formatDecimalID(v.area_cm2)} cm²`
  }
  return `${formatDecimalID(v.area_pct)}%`
}

function areaSubText(v: VisitRecord): string {
  if (v.measure_mode === 'calibrated' && v.area_cm2 !== null) {
    const scalePart =
      v.scale_cm_per_px !== null ? ` · s = ${formatDecimalID(v.scale_cm_per_px, 4)} cm/px` : ''
    return `setara ${formatDecimalID(v.area_pct)}% citra${scalePart}`
  }
  return 'Persentase area pada citra'
}

function deltaLabel(v: VisitRecord): string {
  if (v.delta_area === null || v.delta_area === undefined) return ''
  const unit = v.pac_basis === 'calibrated' ? 'cm²' : 'pp'
  return `ΔA: ${formatSignedDecimalID(v.delta_area, 2)} ${unit}`
}

function trendTagClass(v: VisitRecord, idx: number): string {
  if (visitNumber(v, idx) === 1) return 'neutral'
  const cls = getTrendCssClass(v.trend_status)
  if (cls === 'down') return 'good'
  if (cls === 'up') return 'danger'
  if (cls === 'flat') return 'warn'
  return 'neutral'
}

function activeRowWarnings(v: VisitRecord): WarningMeta[] {
  return buildActiveWarnings(v.warnings, v.pac_basis)
}

function warningTooltip(list: WarningMeta[]): string {
  return list.map((w) => `${w.title}: ${w.text}`).join(' | ')
}

function isLatestRow(idx: number): boolean {
  return idx === props.visits.length - 1
}
</script>

<template>
  <section class="card section" aria-labelledby="t-table">
    <div class="sec-head">
      <h2 id="t-table">Riwayat Kunjungan</h2>
      <p>Urutan kronologis dari baseline di atas hingga kunjungan terbaru di bawah.</p>
    </div>

    <div v-if="visits.length === 0" class="empty-table" role="status">
      Belum ada kunjungan final tersimpan untuk pasien ini.
    </div>

    <div
      v-else
      id="tblScroll"
      class="tbl-scroll"
      tabindex="0"
      role="region"
      aria-label="Tabel riwayat kunjungan, dapat digeser horizontal"
    >
      <table role="table">
        <thead>
          <tr role="row">
            <th role="columnheader" scope="col">Kunjungan</th>
            <th role="columnheader" scope="col">Tanggal</th>
            <th role="columnheader" scope="col">Mode &amp; Estimasi Luas</th>
            <th role="columnheader" scope="col">PAC (vs A₀)</th>
            <th role="columnheader" scope="col">Tren &amp; Peringatan</th>
            <th role="columnheader" scope="col">Aksi</th>
          </tr>
        </thead>
        <tbody id="visitRows" role="rowgroup">
          <tr v-for="(v, idx) in visits" :key="v.id" role="row">
            <td role="cell" data-label="Kunjungan">
              <span class="visit">
                Kunjungan {{ visitNumber(v, idx) }}
                <small v-if="visitNumber(v, idx) === 1">Baseline</small>
              </span>
            </td>

            <td role="cell" data-label="Tanggal">
              {{ formatDateID(v.visit_date) }}
            </td>

            <td role="cell" data-label="Mode & Estimasi Luas">
              <div class="area-cell">
                <span class="modebadge" :class="v.measure_mode === 'calibrated' ? 'cal' : 'rel'">
                  {{ v.measure_mode === 'calibrated' ? 'Terkalibrasi · cm²' : 'Basis Relatif · %' }}
                </span>
                <span class="num">{{ areaText(v) }}</span>
                <small class="sub-line">{{ areaSubText(v) }}</small>
              </div>
            </td>

            <td role="cell" data-label="PAC (vs A₀)">
              <span v-if="visitNumber(v, idx) === 1" class="muted-txt">Titik Acuan (A₀)</span>
              <span v-else-if="v.pac === null" class="muted-txt">Tidak dapat dihitung</span>
              <div v-else class="pac-cell">
                <span class="num">{{ formatSignedDecimalID(v.pac, 1) }}%</span>
                <small class="sub-line">
                  {{ v.pac_basis === 'calibrated' ? 'Basis cm²' : 'Basis Relatif %' }}
                  <template v-if="deltaLabel(v)"> · {{ deltaLabel(v) }}</template>
                </small>
              </div>
            </td>

            <td role="cell" data-label="Tren & Peringatan">
              <div class="tags">
                <span class="tag" :class="trendTagClass(v, idx)">
                  {{ visitNumber(v, idx) === 1 ? 'Kunjungan awal (baseline)' : (v.trend_status || '–') }}
                </span>
                <span
                  v-if="activeRowWarnings(v).length > 0"
                  class="warn-pill"
                  :title="warningTooltip(activeRowWarnings(v))"
                  :aria-label="`Peringatan: ${warningTooltip(activeRowWarnings(v))}`"
                >
                  <svg class="i-warn" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 3 2.5 20h19L12 3Z" />
                    <path d="M12 10v4M12 17h.01" />
                  </svg>
                  <span>{{ activeRowWarnings(v).length }} peringatan</span>
                </span>
              </div>
              <small v-if="activeRowWarnings(v).length > 0" class="warn-names">
                {{ activeRowWarnings(v).map((w) => w.title).join('; ') }}
              </small>
            </td>

            <td role="cell" data-label="Aksi">
              <div class="acts">
                <RouterLink
                  class="btn btn-secondary btn-sm"
                  :to="`/kunjungan/${v.id}`"
                  :aria-label="`Lihat hasil Kunjungan ${visitNumber(v, idx)}`"
                >
                  Lihat Hasil
                </RouterLink>

                <button
                  v-if="allowDelete"
                  class="btn btn-danger-outline btn-sm del-btn"
                  type="button"
                  :disabled="!isLatestRow(idx)"
                  :title="
                    isLatestRow(idx)
                      ? `Hapus rekam Kunjungan ${visitNumber(v, idx)} (LIFO)`
                      : 'Terkunci: hanya kunjungan terakhir yang dapat dihapus (aturan LIFO) untuk menjaga integritas longitudinal.'
                  "
                  :aria-label="
                    isLatestRow(idx)
                      ? `Hapus rekam Kunjungan ${visitNumber(v, idx)}`
                      : `Hapus Kunjungan ${visitNumber(v, idx)} dinonaktifkan karena bukan kunjungan terakhir`
                  "
                  @click="isLatestRow(idx) && emit('requestDelete', v)"
                >
                  {{ isLatestRow(idx) ? 'Hapus' : 'Terkunci' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="tbl-foot">
      Setiap baris mencantumkan mode pengukuran (%) atau terkalibrasi (cm²). Penghapusan kunjungan
      mengikuti aturan Last-In First-Out (LIFO).
    </p>
  </section>
</template>

<style scoped>
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
.section { margin-top: 24px; }
.sec-head { padding: 18px 24px 0; }
.sec-head h2 { margin: 0; font-size: 17px; font-weight: 650; color: var(--navy); }
.sec-head p { margin: 4px 0 0; font-size: 13px; color: var(--text-2); }
.empty-table { padding: 20px 24px; font-size: 14px; color: var(--text-2); }
.tbl-scroll { overflow-x: auto; margin-top: 14px; border-top: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; min-width: 880px; }
th {
  font-size: 12px; font-weight: 650; text-align: left; color: var(--text-2);
  padding: 10px 14px; background: var(--bg); border-bottom: 1px solid var(--border); white-space: nowrap;
}
td { padding: 14px; border-bottom: 1px solid var(--border); vertical-align: middle; font-size: 14px; }
tr:last-child td { border-bottom: 0; }
.visit { font-weight: 650; color: var(--text); }
.visit small { display: block; font-weight: 500; color: var(--muted); font-size: 12px; }
.area-cell, .pac-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; }
.modebadge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; border: 1px solid; white-space: nowrap; }
.modebadge.cal { color: var(--green); background: var(--green-bg); border-color: var(--green-bd); }
.modebadge.rel { color: var(--navy); background: var(--teal-soft); border-color: #bfdcdc; }
.num { font-family: var(--mono); font-variant-numeric: tabular-nums; font-weight: 700; color: var(--navy); font-size: 15px; white-space: nowrap; }
.sub-line { font-size: 12px; color: var(--muted); }
.muted-txt { font-size: 13px; color: var(--text-2); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.tag { display: inline-flex; font-size: 12px; font-weight: 650; padding: 3px 10px; border-radius: 999px; border: 1px solid; white-space: nowrap; }
.tag.neutral { background: #f1f5f9; border-color: var(--border-strong); color: #334155; }
.tag.good { background: var(--green-bg); border-color: var(--green-bd); color: var(--green); }
.tag.warn { background: var(--amber-bg); border-color: var(--amber-bd); color: var(--amber); }
.tag.danger { background: var(--error-bg); border-color: var(--error-bd); color: var(--error); }
.warn-pill {
  display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 650;
  padding: 2px 8px; border-radius: 999px; color: var(--amber);
  background: var(--amber-bg); border: 1px solid var(--amber-bd); cursor: help;
}
.i-warn { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2; }
.warn-names { display: block; margin-top: 4px; font-size: 12px; color: var(--amber); }
.acts { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  min-height: 40px; padding: 0 12px; font: inherit; font-size: 13px; font-weight: 600;
  border-radius: 6px; border: 1px solid transparent; cursor: pointer; text-decoration: none; white-space: nowrap;
}
.btn-secondary { background: var(--surface); color: var(--navy); border-color: var(--border-strong); }
.btn-secondary:hover { border-color: var(--navy); background: var(--bg); }
.btn-danger-outline { background: var(--surface); color: var(--error); border-color: var(--error); }
.btn-danger-outline:hover:not(:disabled) { background: var(--error-bg); }
.btn-danger-outline:disabled { background: #e2e8f0; color: #475569; border-color: #cbd5e1; cursor: not-allowed; }
.tbl-foot { margin: 0; padding: 10px 16px; font-size: 12px; color: var(--muted); border-top: 1px solid var(--border); }
@media (max-width: 767px) {
  .sec-head { padding: 16px 16px 0; }
  .tbl-scroll { overflow: visible; border-top: 0; }
  table, tbody, tr, td { display: block; min-width: 0; width: 100%; }
  thead { display: block; position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  tr { border: 1px solid var(--border); border-radius: 8px; margin: 12px 16px; width: auto; padding: 4px 0; }
  td { display: flex; justify-content: space-between; align-items: center; gap: 12px; border-bottom: 1px solid var(--border); padding: 10px 14px; text-align: right; }
  tr td:last-child { border-bottom: 0; }
  td::before { content: attr(data-label); font-size: 12px; font-weight: 650; color: var(--text-2); text-align: left; flex: none; }
  .area-cell, .pac-cell, .tags, .acts { align-items: flex-end; justify-content: flex-end; }
}
</style>
