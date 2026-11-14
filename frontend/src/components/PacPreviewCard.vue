<script setup lang="ts">
import { computed } from 'vue'
import type { VisitPreview, VisitRecord } from '@/types/patient'
import { formatDecimalID, formatSignedDecimalID } from '@/utils/formatters'
import { buildActiveWarnings, getTrendCssClass } from '@/utils/visitWarnings'

interface Props {
  preview: VisitPreview
  baselineVisit: VisitRecord | null
}

const props = defineProps<Props>()

const isCalibratedBasis = computed(() => props.preview.pac_basis === 'calibrated')

const modeBadgeLabel = computed(() =>
  isCalibratedBasis.value ? 'Terkalibrasi cm²' : 'Basis Relatif %',
)

const pacDisplay = computed(() => {
  if (props.preview.pac === null || props.preview.pac === undefined) {
    return 'Tidak dapat dihitung'
  }
  return `${formatSignedDecimalID(props.preview.pac, 1)}%`
})

const baselineValueText = computed(() => {
  if (!props.baselineVisit) return '–'
  if (isCalibratedBasis.value && props.baselineVisit.area_cm2 !== null) {
    return `${formatDecimalID(props.baselineVisit.area_cm2)} cm²`
  }
  return `${formatDecimalID(props.baselineVisit.area_pct)}%`
})

const deltaText = computed(() => {
  if (props.preview.delta_area === null || props.preview.delta_area === undefined) return '–'
  const signed = formatSignedDecimalID(props.preview.delta_area, 2)
  return isCalibratedBasis.value ? `${signed} cm²` : `${signed} poin persentase`
})

const trendClass = computed(() => getTrendCssClass(props.preview.trend_status))

const activeWarnings = computed(() =>
  buildActiveWarnings(props.preview.warnings, props.preview.pac_basis),
)
</script>

<template>
  <section
    v-if="preview.is_baseline"
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
      <div id="m2" class="m-label">Pratinjau PAC (belum disimpan)</div>
      <span id="pacBasisBadge" class="modebadge" :class="isCalibratedBasis ? 'cal' : 'rel'">
        {{ modeBadgeLabel }}
      </span>
    </div>

    <div id="pacVal" class="m-value" :class="{ na: preview.pac === null }">{{ pacDisplay }}</div>
    <div class="m-sub">
      vs Baseline A₀ ({{ baselineValueText }}) · ΔA: {{ deltaText }}
    </div>

    <span v-if="preview.trend_status" id="pacTrendBadge" class="trend" :class="trendClass">
      <span>{{ preview.pac !== null ? `${pacDisplay} · ` : '' }}{{ preview.trend_status }}</span>
    </span>

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

    <div class="formula">
      <code>PAC = ((A₀ − Aₜ) / A₀) × 100%</code>
      <div>PAC positif: luas luka lebih kecil dari baseline. PAC negatif: lebih besar.</div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.metric {
  padding: 18px 20px;
}
.m-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}
.m-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.modebadge {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid;
  white-space: nowrap;
}
.modebadge.cal {
  color: var(--green);
  background: var(--green-bg);
  border-color: var(--green-bd);
}
.modebadge.rel {
  color: var(--navy);
  background: var(--teal-soft);
  border-color: #bfdcdc;
}
.m-value {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-size: 40px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--navy);
  letter-spacing: -0.02em;
  margin-top: 6px;
}
.m-value.na {
  font-size: 22px;
}
.m-sub {
  font-size: 13px;
  color: var(--text-2);
  margin-top: 4px;
}
.m-note {
  font-size: 13px;
  color: var(--text-2);
  margin: 10px 0 0;
  line-height: 1.6;
}
.trend {
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 12px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--green);
  background: var(--green-bg);
  border: 1px solid var(--green-bd);
  padding: 6px 12px;
  border-radius: 12px;
}
.trend.flat {
  color: var(--amber);
  background: var(--amber-bg);
  border-color: var(--amber-bd);
}
.trend.up {
  color: var(--error);
  background: var(--error-bg);
  border-color: var(--error-bd);
}
.warn {
  margin-top: 12px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--amber);
  background: var(--amber-bg);
  border: 1px solid var(--amber-bd);
  border-radius: 8px;
}
.warn.strong {
  border-width: 2px;
  border-color: var(--amber);
}
.warn b {
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}
.formula {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
}
.formula code {
  font-family: var(--mono);
  color: var(--text);
  font-size: 12px;
}
</style>
