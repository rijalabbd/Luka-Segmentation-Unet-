<script setup lang="ts">
import { computed } from 'vue'
import type { VisitRecord } from '@/types/patient'
import { formatDecimalID, formatSignedDecimalID } from '@/utils/formatters'
import { buildActiveWarnings, getTrendCssClass } from '@/utils/visitWarnings'

interface Props {
  visit: VisitRecord
  baselineVisit: VisitRecord | null
}

const props = defineProps<Props>()

const isBaseline = computed(() => props.visit.visit_index === 1)
const isCalibratedBasis = computed(() => props.visit.pac_basis === 'calibrated')
const isZeroFollowUpArea = computed(
  () =>
    !isBaseline.value &&
    props.visit.pac !== null &&
    (props.visit.confirm_zero_area || props.visit.n_wound_px <= 0 || props.visit.area_pct <= 0),
)

const modeBadgeLabel = computed(() =>
  isCalibratedBasis.value ? 'Terkalibrasi cm²' : 'Basis Relatif %',
)

const pacDisplay = computed(() => {
  if (props.visit.pac === null || props.visit.pac === undefined) {
    return 'PAC tidak dapat dihitung'
  }
  return `${formatSignedDecimalID(props.visit.pac, 1)}%`
})

const baselineValueText = computed(() => {
  if (!props.baselineVisit) return '–'
  if (isCalibratedBasis.value && props.baselineVisit.area_cm2 !== null) {
    return `${formatDecimalID(props.baselineVisit.area_cm2)} cm²`
  }
  return `${formatDecimalID(props.baselineVisit.area_pct)}%`
})

const deltaText = computed(() => {
  if (props.visit.delta_area === null || props.visit.delta_area === undefined) return '–'
  const signed = formatSignedDecimalID(props.visit.delta_area, 2)
  return isCalibratedBasis.value ? `${signed} cm²` : `${signed} poin persentase`
})

const trendClass = computed(() => getTrendCssClass(props.visit.trend_status))

const activeWarnings = computed(() =>
  buildActiveWarnings(props.visit.warnings, props.visit.pac_basis),
)

const scaleRatioText = computed(() => {
  const s0 = props.baselineVisit?.scale_cm_per_px
  const st = props.visit.scale_cm_per_px
  if (!s0 || !st || s0 <= 0) return ''
  return (
    `Skala s₀ = ${formatDecimalID(s0, 4)} cm/px, ` +
    `sₜ = ${formatDecimalID(st, 4)} cm/px, ` +
    `rasio sₜ/s₀ ≈ ${formatDecimalID(st / s0, 2)}. ` +
    'PAC relatif ditampilkan sebagai pembanding terhadap pengukuran tanpa kalibrasi.'
  )
})
</script>

<template>
  <section
    v-if="isBaseline"
    id="pacBaselineCard"
    class="panel metric"
    aria-labelledby="m2-base"
  >
    <div class="m-head">
      <div id="m2-base" class="m-label">Kunjungan Awal (Baseline A₀)</div>
      <span class="modebadge rel">Baseline</span>
    </div>
    <p class="m-note">
      Hasil ini menjadi acuan awal (baseline A₀). Perhitungan PAC dan status tren baru tersedia
      mulai kunjungan kedua.
    </p>
  </section>

  <section v-else id="pacCard" class="panel metric" aria-labelledby="m2">
    <div class="m-head">
      <div id="m2" class="m-label">Perubahan Persentase Area (PAC)</div>
      <span
        v-if="visit.pac !== null"
        id="pacBasisBadge"
        class="modebadge"
        :class="isCalibratedBasis ? 'cal' : 'rel'"
      >
        {{ modeBadgeLabel }}
      </span>
    </div>

    <div id="pacVal" class="m-value" :class="{ na: visit.pac === null }">{{ pacDisplay }}</div>

    <div v-if="visit.pac !== null" id="pacSub" class="m-sub">
      vs Baseline A₀ ({{ baselineValueText }}) · ΔA: {{ deltaText }}
    </div>

    <span v-if="visit.trend_status" id="pacTrendBadge" class="trend" :class="trendClass">
      <span>
        {{ visit.pac !== null ? `${pacDisplay} · ` : '' }}{{ visit.trend_status }}
      </span>
    </span>

    <div v-if="visit.pac === null" id="a0ZeroNotice" class="info-box warn" role="status">
      <div>
        <b>PAC tidak dapat dihitung</b>
        <span>
          Luas awal (baseline A₀) bernilai 0,00%, sehingga perhitungan perubahan persentase tidak
          terdefinisi. Evaluasi klinis mengacu pada luas kunjungan saat ini.
        </span>
      </div>
    </div>

    <div v-if="isZeroFollowUpArea" id="zeroAreaNotice" class="info-box neutral" role="status">
      <div>
        <b>Luas luka terkonfirmasi 0,00%</b>
        <span>
          Luas luka pada masker berjumlah 0 piksel ({{ formatDecimalID(visit.area_pct) }}%). Nilai
          PAC {{ pacDisplay }} mencerminkan penutupan area luka pada citra terhadap baseline A₀.
        </span>
      </div>
    </div>

    <div
      v-for="w in activeWarnings"
      :key="w.code"
      class="warn"
      :class="{ strong: w.strong }"
      :data-code="w.code"
      :role="w.role"
    >
      <div>
        <b>{{ w.title }}</b>
        <span>{{ w.text }}</span>
      </div>
    </div>

    <details v-if="isCalibratedBasis && visit.pac !== null" id="calcDet" class="det">
      <summary>Rincian perhitungan</summary>
      <table>
        <thead>
          <tr>
            <th>Basis</th>
            <th>A₀</th>
            <th>Aₜ</th>
            <th>PAC</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Luas cm²</td>
            <td class="n">
              {{ baselineVisit?.area_cm2 !== null && baselineVisit?.area_cm2 !== undefined ? `${formatDecimalID(baselineVisit.area_cm2)} cm²` : '–' }}
            </td>
            <td class="n">
              {{ visit.area_cm2 !== null ? `${formatDecimalID(visit.area_cm2)} cm²` : '–' }}
            </td>
            <td class="n">{{ formatSignedDecimalID(visit.pac_cm2 ?? visit.pac, 1) }}%</td>
          </tr>
          <tr>
            <td>Luas relatif</td>
            <td class="n">{{ formatDecimalID(baselineVisit?.area_pct) }}%</td>
            <td class="n">{{ formatDecimalID(visit.area_pct) }}%</td>
            <td class="n">{{ formatSignedDecimalID(visit.pac_rel, 1) }}%</td>
          </tr>
        </tbody>
      </table>
      <p v-if="scaleRatioText">{{ scaleRatioText }}</p>
    </details>

    <div class="formula">
      <code>PAC = ((A₀ − Aₜ) / A₀) × 100%</code>
      <div>PAC positif: luas luka lebih kecil dari baseline. PAC negatif: lebih besar.</div>
    </div>
  </section>
</template>

<style scoped>
.panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
.metric { padding: 18px 20px; }
.m-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; flex-wrap: wrap; }
.m-label { font-size: 13px; font-weight: 600; color: var(--text-2); }
.modebadge { font-size: 11.5px; font-weight: 700; padding: 3px 9px; border-radius: 999px; border: 1px solid; white-space: nowrap; }
.modebadge.cal { color: var(--green); background: var(--green-bg); border-color: var(--green-bd); }
.modebadge.rel { color: var(--navy); background: var(--teal-soft); border-color: #bfdcdc; }
.m-value { font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 40px; line-height: 1.15; font-weight: 700; color: var(--navy); letter-spacing: -0.02em; margin-top: 6px; }
.m-value.na { font-size: 22px; }
.m-sub { font-size: 13px; color: var(--text-2); margin-top: 4px; }
.m-note { font-size: 13px; color: var(--text-2); margin: 10px 0 0; line-height: 1.6; }
.trend { display: inline-flex; align-items: flex-start; gap: 6px; margin-top: 12px; font-size: 13px; font-weight: 700; line-height: 1.4; color: var(--green); background: var(--green-bg); border: 1px solid var(--green-bd); padding: 6px 12px; border-radius: 12px; }
.trend.flat { color: var(--amber); background: var(--amber-bg); border-color: var(--amber-bd); }
.trend.up { color: var(--error); background: var(--error-bg); border-color: var(--error-bd); }
.trend.na { color: var(--text-2); background: #f1f5f9; border-color: var(--border-strong); }
.warn, .info-box { margin-top: 12px; padding: 10px 12px; font-size: 13px; line-height: 1.55; color: var(--amber); background: var(--amber-bg); border: 1px solid var(--amber-bd); border-radius: 8px; }
.info-box.neutral { color: var(--navy); background: var(--teal-soft); border-color: #bfdcdc; }
.warn.strong { border-width: 2px; border-color: var(--amber); }
.warn b, .info-box b { display: block; font-weight: 700; margin-bottom: 2px; }
.det { margin-top: 12px; font-size: 12.5px; color: var(--text-2); }
.det summary { cursor: pointer; font-weight: 650; color: var(--teal); min-height: 36px; display: flex; align-items: center; text-align: left; }
.det table { width: 100%; border-collapse: collapse; margin-top: 6px; }
.det th, .det td { text-align: left; padding: 5px 6px; border-bottom: 1px solid var(--border); font-weight: 500; }
.det th { color: var(--muted); font-size: 12px; }
.det td.n { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--navy); font-weight: 700; }
.det p { margin: 8px 0 0; line-height: 1.5; }
.formula { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 12px; color: var(--muted); line-height: 1.6; }
.formula code { font-family: var(--mono); color: var(--text); font-size: 12px; }
</style>
