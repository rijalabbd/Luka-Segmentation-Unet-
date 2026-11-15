<script setup lang="ts">
defineProps<{
  openByDefault: boolean;
}>();
</script>

<template>
  <details id="guide" class="guide-card" :open="openByDefault">
    <summary class="guide-summary">
      <span>Panduan foto</span>
      <span class="guide-chevron" aria-hidden="true">▾</span>
    </summary>
    <div class="guide-body">
      <ol class="guide-list">
        <li>
          <strong>Jarak sama</strong>
          <span>Ambil dari jarak yang sama dengan foto sebelumnya.</span>
        </li>
        <li>
          <strong>Kamera tegak lurus</strong>
          <span>Arahkan lensa sejajar dengan permukaan luka, tidak miring.</span>
        </li>
        <li>
          <strong>Cahaya cukup</strong>
          <span>Pastikan luka terlihat jelas, tanpa bayangan gelap.</span>
        </li>
        <li>
          <strong>Tanpa filter</strong>
          <span>Gunakan kamera biasa tanpa efek atau pemotongan.</span>
        </li>
        <li>
          <strong>Sertakan penggaris</strong>
          <span>Letakkan penggaris di dekat luka bila ingin mengukur dalam cm².</span>
        </li>
      </ol>
    </div>
  </details>
</template>

<style scoped>
.guide-card {
  margin-top: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.guide-summary {
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  min-height: 44px;
  font-size: 14px;
  font-weight: 650;
  color: var(--navy);
  cursor: pointer;
  user-select: none;
}
.guide-summary::-webkit-details-marker {
  display: none;
}
.guide-summary:hover {
  background: var(--bg);
}
.guide-summary:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: -2px;
}
.guide-chevron {
  font-size: 14px;
  color: var(--text-muted);
  transition: transform var(--dur);
}
.guide-card[open] .guide-chevron {
  transform: rotate(180deg);
}
.guide-body {
  padding: 0 20px 18px;
  border-top: 1px solid var(--border);
}
.guide-list {
  margin: 14px 0 0;
  padding-left: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px 20px;
  font-size: 13.5px;
  line-height: 1.45;
  color: var(--text-2);
}
.guide-list li strong {
  display: block;
  color: var(--navy);
  font-weight: 600;
}
@media (prefers-reduced-motion: reduce) {
  .guide-chevron {
    transition: none;
  }
}
@media (max-width: 640px) {
  .guide-summary {
    padding: 12px 16px;
  }
  .guide-body {
    padding: 0 16px 16px;
  }
}
</style>
