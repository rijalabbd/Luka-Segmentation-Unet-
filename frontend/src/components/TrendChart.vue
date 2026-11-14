<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { VisitRecord } from '@/types/patient'
import { formatDateID, formatSignedDecimalID } from '@/utils/formatters'
import { computeTrendChartModel, type ChartPoint, type ChartSeries } from '@/utils/trendChart'

interface Props {
  visits: VisitRecord[]
  patientId: string
}

const props = defineProps<Props>()

const wrapRef = ref<HTMLDivElement | null>(null)
const containerWidth = ref(720)
const hoveredTip = ref<{
  x: number
  y: number
  title: string
  detail: string
  area: string
} | null>(null)

let resizeObserver: ResizeObserver | null = null

function updateWidth() {
  if (!wrapRef.value) return
  const w = Math.floor(wrapRef.value.clientWidth - 8)
  if (w > 220) containerWidth.value = w
}

onMounted(() => {
  updateWidth()
  if (typeof ResizeObserver !== 'undefined' && wrapRef.value) {
    resizeObserver = new ResizeObserver(() => updateWidth())
    resizeObserver.observe(wrapRef.value)
  } else {
    window.addEventListener('resize', updateWidth)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', updateWidth)
})

const isCompact = computed(() => containerWidth.value < 500)
const model = computed(() =>
  computeTrendChartModel(props.visits, containerWidth.value, isCompact.value),
)

const tooltipStyle = computed(() => {
  if (!hoveredTip.value) return {}
  const left = Math.min(Math.max(8, hoveredTip.value.x - 80), Math.max(8, model.value.width - 210))
  const top = Math.max(8, hoveredTip.value.y - 68)
  return { left: `${left}px`, top: `${top}px` }
})

function formatPointPacLabel(p: ChartPoint): string {
  if (p.visitNumber === 1) return 'A₀ 0,0%'
  return `${formatSignedDecimalID(p.pac, 1)}%`
}

function pointFill(series: ChartSeries, p: ChartPoint): string {
  if (series.id === 'relative' && model.value.mode === 'mixed_dual') return '#ffffff'
  if (
    series.id === 'relative' &&
    model.value.hasMixedMeasurementModes &&
    p.measureMode === 'calibrated'
  ) {
    return '#eaf4f4'
  }
  return '#ffffff'
}

function pointStroke(series: ChartSeries, p: ChartPoint): string {
  if (series.id === 'calibrated') return '#2A6F73'
  if (p.measureMode === 'calibrated') return '#2A6F73'
  return '#0F2942'
}

function showTip(series: ChartSeries, p: ChartPoint) {
  hoveredTip.value = {
    x: p.x,
    y: p.y,
    title: `Kunjungan ${p.visitNumber} · ${formatDateID(p.visitDate)}`,
    detail: `${series.id === 'calibrated' ? 'PAC cm²' : 'PAC relatif'}: ${
      p.visitNumber === 1 ? '0,0% (baseline)' : `${formatSignedDecimalID(p.pac, 1)}%`
    }`,
    area: `Luas: ${p.areaText}${
      p.measureMode === 'calibrated' && series.id === 'relative' ? ' (foto terkalibrasi)' : ''
    }`,
  }
}

function hideTip() {
  hoveredTip.value = null
}
</script>

<template>
  <section class="card section" aria-labelledby="t-chart">
    <div class="sec-head">
      <h2 id="t-chart">Perkembangan PAC terhadap Baseline A₀ ({{ patientId }})</h2>
      <p>
        <strong>Garis menanjak menandakan pengecilan area luka (PAC positif terhadap A₀).</strong>
      </p>
    </div>

    <div ref="wrapRef" class="chart-wrap">
      <div v-if="model.mode === 'empty'" id="chartEmptyState" class="chart-state">
        Belum ada kunjungan final tersimpan. Grafik tren PAC akan tampil setelah pemeriksaan pertama
        dan kedua disimpan.
      </div>

      <div v-else-if="model.mode === 'baseline_only'" id="chartBaselineState" class="chart-state">
        <b>PAC dihitung mulai kunjungan kedua.</b>
        <span>
          Kunjungan pertama ({{ formatDateID(props.visits[0]?.visit_date) }}) menetapkan luas
          baseline A₀. Grafik garis tren otomatis digambar setelah kunjungan kedua disimpan.
        </span>
      </div>

      <div v-else class="svg-host">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          :width="model.width"
          :height="model.height"
          :viewBox="`0 0 ${model.width} ${model.height}`"
          role="img"
          :aria-label="model.ariaLabel"
          aria-labelledby="ch-t ch-d"
          focusable="false"
        >
          <title id="ch-t">Lintasan PAC terhadap baseline A₀ pasien {{ patientId }}</title>
          <desc id="ch-d">{{ model.description }}</desc>

          <text class="axt" :x="model.plotLeft" y="16">PAC terhadap A₀ (%)</text>

          <g v-for="t in model.ticks" :key="t.value">
            <line
              :x1="model.plotLeft"
              :x2="model.plotRight"
              :y1="t.y"
              :y2="t.y"
              :stroke="t.isZero ? '#94A3B8' : '#E2E8F0'"
              :stroke-width="t.isZero ? 1.5 : 1"
            />
            <text class="tk" :x="model.plotLeft - 8" :y="t.y + 4" text-anchor="end">
              {{ t.label }}
            </text>
          </g>

          <g v-for="s in model.series" :key="s.id">
            <polyline
              v-if="s.points.length >= 2"
              fill="none"
              :stroke="s.stroke"
              stroke-width="3"
              stroke-linejoin="round"
              stroke-linecap="round"
              :stroke-dasharray="s.dashed ? '6 5' : undefined"
              :points="s.polylinePoints"
            />

            <g
              v-for="p in s.points"
              :key="`${s.id}-${p.visitId}`"
              class="pt"
              tabindex="0"
              :aria-label="`Kunjungan ${p.visitNumber}, ${formatDateID(p.visitDate)}, ${p.pacBasisLabel}: ${formatPointPacLabel(p)}, luas ${p.areaText}`"
              @mouseenter="showTip(s, p)"
              @mouseleave="hideTip"
              @focus="showTip(s, p)"
              @blur="hideTip"
            >
              <circle
                :cx="p.x"
                :cy="p.y"
                r="6"
                :fill="pointFill(s, p)"
                :stroke="pointStroke(s, p)"
                stroke-width="3"
              />
              <circle :cx="p.x" :cy="p.y" r="14" fill="transparent" />
              <text
                v-if="!(model.mode === 'mixed_dual' && s.id === 'relative' && p.visitNumber === 1)"
                class="vl"
                :x="p.x"
                :y="p.y - 13 - (s.id === 'relative' && model.mode === 'mixed_dual' ? 16 : p.staggerTop * 18)"
                text-anchor="middle"
              >
                {{ formatPointPacLabel(p) }}
              </text>
              <text
                v-if="s.id === model.series[0]?.id"
                class="al"
                :x="p.x"
                :y="p.y + 24 + p.staggerBottom * 16"
                text-anchor="middle"
              >
                {{ isCompact ? '' : 'luas ' }}{{ p.areaText }}
              </text>
            </g>
          </g>

          <g v-for="xv in model.xAxisVisits" :key="`x-${xv.visitId}`">
            <text
              class="xl"
              :x="xv.x"
              :y="model.xAxisLabelY + xv.staggerX * 32"
              text-anchor="middle"
            >
              K{{ xv.visitNumber }}
            </text>
            <text
              class="xd"
              :x="xv.x"
              :y="model.xAxisLabelY + 16 + xv.staggerX * 32"
              text-anchor="middle"
            >
              {{ xv.shortDate }}
            </text>
          </g>
        </svg>

        <div v-if="hoveredTip" class="chart-tip" role="tooltip" :style="tooltipStyle">
          <b>{{ hoveredTip.title }}</b>
          <div>{{ hoveredTip.detail }}</div>
          <div>{{ hoveredTip.area }}</div>
        </div>
      </div>
    </div>

    <div v-if="model.series.length > 0" class="chart-legend">
      <template v-if="model.mode === 'single_calibrated'">
        <span><i class="lg-line cal"></i>PAC terkalibrasi cm² (%) terhadap A₀</span>
        <span><i class="lg-dot cal"></i>Kunjungan terkalibrasi (cm²)</span>
      </template>
      <template v-else-if="model.mode === 'mixed_dual'">
        <span><i class="lg-line cal"></i>Seri 1: PAC terkalibrasi cm² (%)</span>
        <span><i class="lg-line dash"></i>Seri 2: PAC relatif luas citra (%)</span>
        <span>Titik cm² hanya digambar pada kunjungan yang terkalibrasi bersama baseline A₀</span>
      </template>
      <template v-else>
        <span><i class="lg-line"></i>PAC relatif luas citra (%) terhadap A₀</span>
        <span><i class="lg-dot"></i>Titik kunjungan relatif</span>
        <span v-if="model.hasMixedMeasurementModes">
          <i class="lg-dot mixed"></i>Foto terkalibrasi, PAC tetap memakai basis relatif (%) karena A₀ relatif
        </span>
      </template>
      <span>Sumbu X mengikuti jarak hari antar-pemeriksaan</span>
    </div>
  </section>
</template>

<style scoped>
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
.section { margin-top: 24px; }
.sec-head { padding: 18px 24px 0; }
.sec-head h2 { margin: 0; font-size: 17px; font-weight: 650; color: var(--navy); }
.sec-head p { margin: 4px 0 0; font-size: 13px; color: var(--text-2); }
.sec-head p strong { color: var(--green); font-weight: 650; }
.chart-wrap { padding: 10px 8px 12px; position: relative; overflow: hidden; }
.svg-host { position: relative; }
.chart-wrap svg { display: block; max-width: 100%; }
.chart-wrap text { font-family: var(--sans); font-size: 12px; fill: var(--muted); }
.chart-wrap .axt { fill: var(--text-2); font-weight: 600; }
.chart-wrap .tk { font-family: var(--mono); }
.chart-wrap .xl { fill: var(--text); font-weight: 650; }
.chart-wrap .xd { font-family: var(--mono); font-size: 11.5px; }
.chart-wrap .vl { font-family: var(--mono); font-weight: 700; fill: var(--navy); }
.chart-wrap .al { font-family: var(--mono); font-size: 11px; fill: var(--text-2); }
.chart-wrap .vl, .chart-wrap .al { paint-order: stroke; stroke: #fff; stroke-width: 4px; stroke-linejoin: round; }
.pt { cursor: pointer; outline: none; }
.pt:focus-visible circle:first-child { stroke-width: 4; }
.chart-state {
  margin: 8px 16px; padding: 16px 18px; border-radius: 8px;
  background: var(--bg); border: 1px dashed var(--border-strong);
  font-size: 14px; color: var(--text-2); line-height: 1.6;
}
.chart-state b { display: block; color: var(--navy); margin-bottom: 4px; }
.chart-tip {
  position: absolute; z-index: 10; pointer-events: none;
  background: var(--navy); color: #fff; font-size: 12px; line-height: 1.45;
  padding: 8px 10px; border-radius: 6px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.25);
  white-space: nowrap;
}
.chart-legend {
  display: flex; gap: 6px 18px; flex-wrap: wrap; padding: 0 24px 18px;
  font-size: 12px; color: var(--text-2);
}
.chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
.lg-line { width: 18px; height: 3px; background: var(--teal); border-radius: 2px; display: inline-block; }
.lg-line.cal { background: #2a6f73; }
.lg-line.dash { height: 0; border-top: 3px dashed var(--navy); background: none; }
.lg-dot {
  width: 10px; height: 10px; border-radius: 50%; border: 3px solid var(--navy);
  background: #fff; display: inline-block;
}
.lg-dot.cal { border-color: #2a6f73; }
.lg-dot.mixed { border-color: #2a6f73; background: #eaf4f4; }
@media (max-width: 767px) {
  .sec-head { padding: 16px 16px 0; }
  .chart-legend { padding: 0 16px 16px; }
}
</style>
