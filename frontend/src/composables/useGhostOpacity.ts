import { ref, watch } from 'vue';

export const GHOST_OPACITY_MIN = 0;
export const GHOST_OPACITY_MAX = 80;
export const GHOST_OPACITY_STEP = 5;
export const GHOST_OPACITY_DEFAULT = 40;

export const STAGE1_OPACITY_STORAGE_KEY = 'woundai.h3.ghostOpacity';
export const CAMERA_OPACITY_STORAGE_KEY = 'woundai.h3.cameraGhostOpacity';

export function clampGhostOpacity(value: number): number {
  if (!Number.isFinite(value)) return GHOST_OPACITY_DEFAULT;
  return Math.min(GHOST_OPACITY_MAX, Math.max(GHOST_OPACITY_MIN, Math.round(value)));
}

function readStoredOpacity(storageKey: string, fallback: number): number {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw === null) return fallback;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? clampGhostOpacity(parsed) : fallback;
  } catch {
    return fallback;
  }
}

function writeStoredOpacity(storageKey: string, value: number): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, String(clampGhostOpacity(value)));
  } catch {
    // Abaikan kegagalan storage pada mode privat / kuota penuh
  }
}

export function useGhostOpacity(
  storageKey: string,
  initialValue = GHOST_OPACITY_DEFAULT,
) {
  const defaultVal = clampGhostOpacity(initialValue);
  const opacity = ref<number>(readStoredOpacity(storageKey, defaultVal));

  watch(opacity, (val) => {
    const clamped = clampGhostOpacity(val);
    if (clamped !== val) {
      opacity.value = clamped;
      return;
    }
    writeStoredOpacity(storageKey, clamped);
  });

  function resetOpacity() {
    opacity.value = defaultVal;
  }

  return {
    opacity,
    resetOpacity,
    min: GHOST_OPACITY_MIN,
    max: GHOST_OPACITY_MAX,
    step: GHOST_OPACITY_STEP,
  };
}
