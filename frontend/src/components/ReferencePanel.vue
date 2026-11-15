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
}>();

const emit = defineEmits<{
  (e: 'update:activeRefTab', value: 'baseline' | 'latest'): void;
  (e: 'update:showContour', value: boolean): void;
}>();

const isZoomOpen = ref(false);

const refTitle = computed(() => {
  const prefix = props.activeRefTab === 'latest' && props.hasDistinctLatest ? 'Foto terakhir' : 'Foto awal';
  return props.activeDateLabel ? `${prefix} · ${props.activeDateLabel}` : prefix;
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
      <button
        id="ref-open"
        type="button"
        class="ref-thumb"
        :aria-label="`Perbesar ${refTitle}`"
        @click="isZoomOpen = true"
      >
        <img id="ref-img" :src="displayedImageUrl || activeImageUrl" :alt="refTitle" />
        <span class="zoom">Perbesar</span>
      </button>

      <div class="ref-meta">
        <div class="ref-head">
          <p class="ref-caption">{{ refTitle }}</p>
          <button
            v-if="hasDistinctLatest"
            type="button"
            class="ref-switch"
            @click="toggleRefSource"
          >
            {{ activeRefTab === 'latest' ? 'Kembali ke foto awal' : `Lihat foto terakhir (${latestShortDate})` }}
          </button>
        </div>
        <p class="ref-help">Samakan jarak dan sudut kamera dengan foto ini.</p>

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
    </template>

    <template v-else>
      <p class="ref-missing">
        Foto kunjungan {{ activeDateLabel }} tidak tersimpan, jadi belum ada pembanding. Ikuti panduan foto di bawah.
      </p>
      <button
        v-if="hasDistinctLatest"
        type="button"
        class="ref-switch"
        @click="toggleRefSource"
      >
        {{ activeRefTab === 'latest' ? 'Kembali ke foto awal' : `Lihat foto terakhir (${latestShortDate})` }}
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
      </div>
    </div>
  </section>
</template>

<style scoped>
.ref-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ref-thumb {
  position: relative;
  width: 100%;
  height: 155px;
  max-height: 170px;
  padding: 0;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  overflow: hidden;
  cursor: zoom-in;
  background: #f8fafc;
}
.ref-thumb:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.ref-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.ref-thumb .zoom {
  position: absolute;
  right: 8px;
  bottom: 8px;
  background: rgba(15, 41, 66, 0.88);
  color: #fff;
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
}
.ref-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.ref-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px 12px;
  flex-wrap: wrap;
}
.ref-caption {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--navy);
}
.ref-help {
  margin: 0;
  font-size: 13px;
  color: var(--text-2);
}
.contour-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  font-size: 13px;
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
  max-height: 75vh;
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
  padding: 0 18px;
  font: inherit;
  font-size: 14px;
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
