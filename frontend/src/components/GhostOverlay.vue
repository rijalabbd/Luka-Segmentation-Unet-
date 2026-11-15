<script setup lang="ts">
defineProps<{
  previewUrl: string;
  fileName: string;
  fileSizeText: string;
  refImageUrl: string | null;
  ghostActive: boolean;
  ghostOpacity: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: 'replace'): void;
}>();
</script>

<template>
  <div id="preview" class="preview-wrap">
    <div id="stack" class="frame">
      <img id="img" :src="previewUrl" alt="Pratinjau foto luka yang dipilih" />
      <img
        v-if="ghostActive && refImageUrl"
        id="ghost"
        :src="refImageUrl"
        alt=""
        aria-hidden="true"
        class="ghost-img"
        :style="{ opacity: ghostOpacity / 100 }"
      />
    </div>

    <div class="fileinfo">
      <div class="file-meta">
        <span id="fname" class="fname">{{ fileName }}</span>
        <span id="fsize" class="fsize">{{ fileSizeText }}</span>
      </div>
      <div class="fileinfo-actions">
        <span class="fcheck">✓ Foto siap</span>
        <button
          id="replace"
          type="button"
          class="btn btn-sm"
          :disabled="disabled"
          @click="emit('replace')"
        >
          Ganti Foto
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.frame {
  position: relative;
  width: 100%;
  height: 155px;
  max-height: 170px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}
.frame img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.ghost-img {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.fileinfo {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px 12px;
  flex-wrap: wrap;
}
.file-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.fname {
  font-size: 13px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fsize {
  font-size: 12.5px;
  color: var(--text-muted);
  flex: none;
}
.fileinfo-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}
.fcheck {
  font-size: 13px;
  color: var(--ok);
  font-weight: 600;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 12px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--navy);
  cursor: pointer;
}
.btn:hover:not(:disabled) {
  border-color: var(--navy);
  background: var(--bg);
}
.btn:focus-visible {
  outline: 2px solid var(--navy);
  outline-offset: 2px;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
