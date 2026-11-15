<script setup lang="ts">
import { computed } from 'vue'
import type { VisitRecord } from '@/types/patient'
import PacComparisonBody from './PacComparisonBody.vue'

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

const awalArea = computed(() => {
  if (!props.baselineVisit) return null
  return isCalibratedBasis.value ? props.baselineVisit.area_cm2 : props.baselineVisit.area_pct
})

const sekarangArea = computed(() =>
  isCalibratedBasis.value ? props.visit.area_cm2 : props.visit.area_pct,
)
</script>

<template>
  <PacComparisonBody
    v-if="!isBaseline"
    :pac-basis="visit.pac_basis"
    :pac="visit.pac"
    :delta-area="visit.delta_area"
    :trend-status="visit.trend_status"
    :warnings="visit.warnings"
    :awal-area="awalArea"
    :sekarang-area="sekarangArea"
    :is-zero-follow-up-area="isZeroFollowUpArea"
  />
</template>
