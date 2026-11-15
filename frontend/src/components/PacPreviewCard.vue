<script setup lang="ts">
import { computed } from 'vue'
import type { VisitPreview, VisitRecord } from '@/types/patient'
import PacComparisonBody from './PacComparisonBody.vue'

interface Props {
  preview: VisitPreview
  baselineVisit: VisitRecord | null
  currentAreaPct: number
  currentAreaCm2: number | null
}

const props = defineProps<Props>()

const isCalibratedBasis = computed(() => props.preview.pac_basis === 'calibrated')

const awalArea = computed(() => {
  if (!props.baselineVisit) return null
  return isCalibratedBasis.value ? props.baselineVisit.area_cm2 : props.baselineVisit.area_pct
})

const sekarangArea = computed(() =>
  isCalibratedBasis.value ? props.currentAreaCm2 : props.currentAreaPct,
)
</script>

<template>
  <PacComparisonBody
    v-if="!preview.is_baseline"
    :pac-basis="preview.pac_basis"
    :pac="preview.pac"
    :delta-area="preview.delta_area"
    :trend-status="preview.trend_status"
    :warnings="preview.warnings"
    :awal-area="awalArea"
    :sekarang-area="sekarangArea"
  />
</template>
