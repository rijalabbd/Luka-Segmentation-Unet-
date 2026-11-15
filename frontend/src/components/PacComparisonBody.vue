<script setup lang="ts">
import { computed } from 'vue'
import { formatSignedDecimalID } from '@/utils/formatters'
import {
  buildActiveWarnings,
  buildAreaComparisonBars,
  formatTrendSummary,
} from '@/utils/visitWarnings'

interface Props {
  pacBasis: 'relative' | 'calibrated' | null
  pac: number | null
  deltaArea: number | null
  trendStatus: string | null
  warnings: string[] | null | undefined
  awalArea: number | null
  sekarangArea: number | null
  isZeroFollowUpArea?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isZeroFollowUpArea: false,
})

const isCalibratedBasis = computed(() => props.pacBasis === 'calibrated')

const trendSummary = computed(() => formatTrendSummary(props.trendStatus, props.pac))

const pacTooltipText = computed(() => {
  if (props.pac === null || props.pac === undefined || Number.isNaN(props.pac)) {
    return 'Selisih luas awal dan luas sekarang, dibagi luas awal.'
  }
  const signed = `${formatSignedDecimalID(props.pac, 1)}%`
  const meaning =
    props.pac < 0
      ? 'Negatif = luka membesar.'
      : props.pac > 0
        ? 'Positif = luka mengecil.'
        : 'Nol = luas tidak berubah.'
  return `Perubahan luas (PAC): ${signed}. ${meaning}`
})

const bars = computed(() =>
  buildAreaComparisonBars({
    awal: props.awalArea,
    sekarang: props.sekarangArea,
    unit: isCalibratedBasis.value ? ' cm²' : '%',
  }),
)

const activeWarnings = computed(() => buildActiveWarnings(props.warnings, props.pacBasis))

const distanceWarnings = computed(() =>
  activeWarnings.value.filter(
    (w) => w.code === 'DISTANCE_SENSITIVE' || w.code === 'DISTANCE_LARGE',
  ),
)

const otherWarnings = computed(() =>
  activeWarnings.value.filter(
    (w) => w.code !== 'DISTANCE_SENSITIVE' && w.code !== 'DISTANCE_LARGE',
  ),
)
</script>

<template>
  <section id="pacCard" class="panel metric" aria-labelledby="m2">
    <div class="m-head">
      <div class="m-title-group">
        <div id="m2" class="m-label">Perubahan luas</div>
        <details class="info-pop">
          <summary aria-label="Info perhitungan perubahan luas">?</summary>
          <div id="pacTooltipBody" class="info-pop-body" role="note">
            {{ pacTooltipText }}
          </div>
        </details>
      </div>
      <span id="modeBadge" class="modebadge" :class="isCalibratedBasis ? 'cal' : 'rel'">
        {{ isCalibratedBasis ? 'Terkalibrasi cm²' : 'Dari foto' }}
      </span>
    </div>

    <div id="pacTrendBadge" class="status-hero" :class="trendSummary.cssClass">
      <div class="status-main">
        <span class="status-arrow" aria-hidden="true">{{ trendSummary.arrow }}</span>
        <span id="pacTrendHeadline">{{ trendSummary.headline }}</span>
      </div>
      <p class="status-neutral">Hasil dari foto. Dokter akan menilai langsung.</p>
    </div>

    <div
      v-for="w in distanceWarnings"
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

    <div v-if="bars.length" class="bars" role="group" aria-label="Perbandingan luas awal dan sekarang">
      <div v-for="bar in bars" :key="bar.key" class="bar-row" :data-bar="bar.key">
        <span class="bar-label">{{ bar.label }}</span>
        <div class="bar-track" aria-hidden="true">
          <div
            class="bar-fill"
            :class="[bar.key, bar.key === 'sekarang' ? trendSummary.cssClass : '']"
            :style="{ width: `${bar.widthPct}%` }"
          ></div>
        </div>
        <span class="bar-val">{{ bar.valueText }}</span>
      </div>
    </div>

    <div v-if="pac === null" id="a0ZeroNotice" class="info-box warn" role="status">
      <div>
        <b>Perubahan luas belum dapat dihitung</b>
        <span>
          Luas pemeriksaan pertama bernilai 0,0%, sehingga persentase perubahan tidak dapat dihitung.
        </span>
      </div>
    </div>

    <div v-if="isZeroFollowUpArea" id="zeroAreaNotice" class="info-box neutral" role="status">
      <div>
        <b>Luas luka tercatat 0,0%</b>
        <span>Luas luka pada foto tercatat 0 piksel (0,0%).</span>
      </div>
    </div>

    <div
      v-for="w in otherWarnings"
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
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.m-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.m-label {
  font-size: 14px;
  font-weight: 650;
  color: var(--text-2);
}
.modebadge {
  font-size: 14px;
  font-weight: 700;
  padding: 3px 10px;
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
.info-pop {
  position: relative;
  display: inline-block;
}
.info-pop summary {
  list-style: none;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  background: var(--bg);
  color: var(--navy);
  font-size: 14px;
  font-weight: 700;
  display: grid;
  place-items: center;
  cursor: pointer;
  user-select: none;
}
.info-pop summary::-webkit-details-marker {
  display: none;
}
.info-pop summary:hover {
  border-color: var(--navy);
}
.info-pop-body {
  position: absolute;
  left: 0;
  top: calc(100% + 6px);
  width: min(260px, 75vw);
  z-index: 15;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  box-shadow: 0 8px 20px rgba(15, 41, 66, 0.14);
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-2);
}
.status-hero {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid var(--green-bd);
  background: var(--green-bg);
  color: var(--green);
}
.status-hero.flat {
  color: var(--amber);
  background: var(--amber-bg);
  border-color: var(--amber-bd);
}
.status-hero.up {
  color: var(--error);
  background: var(--error-bg);
  border-color: var(--error-bd);
}
.status-hero.na {
  color: var(--text-2);
  background: #f1f5f9;
  border-color: var(--border-strong);
}
.status-main {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.25;
}
.status-arrow {
  font-size: 22px;
  line-height: 1;
}
.status-neutral {
  margin: 6px 0 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
  line-height: 1.45;
}
.bars {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}
.bar-row {
  display: grid;
  grid-template-columns: 74px 1fr auto;
  align-items: center;
  gap: 10px;
}
.bar-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-2);
}
.bar-track {
  height: 12px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
}
.bar-fill.awal {
  background: #64748b;
}
.bar-fill.sekarang.down {
  background: var(--green);
}
.bar-fill.sekarang.flat {
  background: var(--amber);
}
.bar-fill.sekarang.up {
  background: var(--error);
}
.bar-fill.sekarang.na {
  background: var(--navy);
}
.bar-val {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  font-size: 14px;
  font-weight: 700;
  color: var(--navy);
  min-width: 66px;
  text-align: right;
}
.warn,
.info-box {
  margin-top: 12px;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--amber);
  background: var(--amber-bg);
  border: 1px solid var(--amber-bd);
  border-radius: 8px;
}
.info-box.neutral {
  color: var(--navy);
  background: var(--teal-soft);
  border-color: #bfdcdc;
}
.warn.strong {
  border-width: 2px;
  border-color: var(--amber);
}
.warn b,
.info-box b {
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}
</style>
