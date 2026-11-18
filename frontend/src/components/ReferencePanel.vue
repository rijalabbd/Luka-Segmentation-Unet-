<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

const props = defineProps<{
  activeRefTab: 'baseline' | 'latest';
  hasDistinctLatest: boolean;
  activeDateLabel: string;
  latestShortDate: string;
  activeImageUrl: string | null;
  activeOverlayUrl: string | null;
  showContour: boolean;
  comparisonSentence?: string;
  missingPhotoSentence?: string;
}>();

const emit = defineEmits<{
  (e: 'update:activeRefTab', value: 'baseline' | 'latest'): void;
  (e: 'update:showContour', value: boolean): void;
}>();

const isZoomOpen = ref(false);

const refTitle = computed(() => {
  const prefix = props.activeRefTab === 'latest' && props.hasDistinctLatest ? 'Foto terakhir' : 'Foto awal';
  return props.activeDateLabel ? `${prefix} ${props.activeDateLabel}` : prefix;
});

const displayedImageUrl = computed(() => {
  if (props.showContour && props.activeOverlayUrl) {
    return props.activeOverlayUrl;
  }
  return props.activeImageUrl;
});

function toggleRefSource() {
  emit('update:activeRefTab', props.activeRefTab === 'latest' ? 'baseline' : 'latest');
}

function handleContourChange(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  emit('update:showContour', checked);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isZoomOpen.value) {
    isZoomOpen.value = false;
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <section id="ref" class="ref-panel" aria-label="Foto pembanding">
    <template v-if="activeImageUrl">
      <div class="ref-compact-row">
        <img
          id="ref-img"
          class="ref-thumb-sm"
          :src="displayedImageUrl || activeImageUrl"
          :alt="refTitle"
          @click="isZoomOpen = true"
        />

        <div class="ref-compact-body">
          <p class="ref-caption">{{ refTitle }}</p>
          <button
            v-if="hasDistinctLatest"
            type="button"
            class="ref-switch"
            @click="toggleRefSource"
          >
            {{ activeRefTab === 'latest' ? 'Lihat foto awal' : `Lihat foto terakhir (${latestShortDate})` }}
          </button>
        </div>

        <button
          id="ref-open"
          type="button"
          class="btn ref-open-btn"
          :aria-label="`Perbesar ${refTitle}`"
          @click="isZoomOpen = true"
        >
          Perbesar
        </button>
      </div>

      <p v-if="missingPhotoSentence" class="ref-missing ref-missing-sub">{{ missingPhotoSentence }}</p>
    </template>

    <template v-else>
      <p class="ref-missing">
        {{
          comparisonSentence ||
          'Belum ada foto pembanding dari kunjungan sebelumnya. Ikuti panduan foto di bawah.'
        }}
      </p>
      <p v-if="missingPhotoSentence" class="ref-missing ref-missing-sub">
        {{ missingPhotoSentence }}
      </p>
      <button
        v-if="hasDistinctLatest"
        type="button"
        class="ref-switch"
        @click="toggleRefSource"
      >
        {{ activeRefTab === 'latest' ? 'Lihat foto awal' : `Lihat foto terakhir (${latestShortDate})` }}
      </button>
    </template>

    <div
      v-if="isZoomOpen && displayedImageUrl"
      id="zoom"
      class="modal-back"
      role="dialog"
      aria-modal="true"
      :aria-label="refTitle"
      @click.self="isZoomOpen = false"
    >
      <div class="modal wide">
        <div class="cap">
          <h2>{{ refTitle }}</h2>
          <button id="z-close" type="button" class="btn" @click="isZoomOpen = false">Tutup</button>
        </div>
        <img :src="displayedImageUrl" :alt="refTitle" />
        <label v-if="activeOverlayUrl" class="contour-toggle">
          <input
            id="toggle-ref-contour"
            type="checkbox"
            :checked="showContour"
            @change="handleContourChange"
          />
          <span>Tampilkan garis tepi luka</span>
        </label>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ref-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ref-compact-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
}
.ref-thumb-sm {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  flex: none;
  cursor: zoom-in;
}
.ref-compact-body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ref-caption {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--navy);
  line-height: 1.3;
}
.ref-open-btn {
  flex: none;
  padding: 0 12px;
}
.contour-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--navy);
  cursor: pointer;
}
.contour-toggle input {
  width: 18px;
  height: 18px;
  accent-color: var(--navy);
  cursor: pointer;
}
.ref-switch {
  align-self: flex-start;
  background: none;
  border: 0;
  padding: 4px 0;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--teal);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.ref-switch:hover {
  color: var(--navy);
}
.ref-switch:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
  border-radius: 3px;
}
.ref-missing {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--text-2);
}
.ref-missing-sub {
  margin-top: 2px;
  color: var(--text-muted);
}
.modal-back {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 50;
}
.modal.wide {
  background: #fff;
  border-radius: 10px;
  max-width: 760px;
  width: 100%;
  padding: 18px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}
.modal.wide img {
  display: block;
  width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid var(--border);
}
.modal.wide .cap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.modal.wide .cap h2 {
  margin: 0;
  font-size: 16px;
  color: var(--navy);
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0 14px;
  font: inherit;
  font-size: 13.5px;
  font-weight: 600;
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--navy);
  cursor: pointer;
}
.btn:hover {
  border-color: var(--navy);
  background: var(--bg);
}
.btn:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
</style>
