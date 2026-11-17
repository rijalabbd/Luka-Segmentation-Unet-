<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  CAMERA_OPACITY_STORAGE_KEY,
  GHOST_OPACITY_MAX,
  GHOST_OPACITY_MIN,
  GHOST_OPACITY_STEP,
  useGhostOpacity,
} from '@/composables/useGhostOpacity';
import { computeCoverCropRect } from '@/utils/cameraCrop';

const props = withDefaults(
  defineProps<{
    refImageUrl?: string | null;
    refLabel?: string;
  }>(),
  {
    refImageUrl: null,
    refLabel: 'awal',
  },
);

const emit = defineEmits<{
  (e: 'capture', file: File): void;
  (e: 'cancel'): void;
  (e: 'fallback', reason: string): void;
}>();

const videoRef = ref<HTMLVideoElement | null>(null);
const isPreparing = ref(true);
const cameraError = ref('');
const captureError = ref('');
const hasMultipleCameras = ref(false);
const supportsTorch = ref(false);
const isTorchOn = ref(false);
const facingMode = ref<'environment' | 'user'>('environment');
const showGrid = ref(false);
const isShadowHidden = ref(false);

const capturedFile = ref<File | null>(null);
const capturedPreviewUrl = ref('');

const { opacity: shadowOpacity } = useGhostOpacity(CAMERA_OPACITY_STORAGE_KEY);

// MediaStream disimpan di variabel biasa (non-reaktif) agar tidak dibungkus Proxy Vue
let activeStream: MediaStream | null = null;
let previousHtmlOverflow = '';
let previousBodyOverflow = '';
let isScrollLocked = false;
let isUnmounted = false;

const hasRefImage = computed(() => Boolean(props.refImageUrl));
const effectiveShadowOpacity = computed(() =>
  isShadowHidden.value ? 0 : shadowOpacity.value / 100,
);
const shadowBadgeText = computed(() => `Bayangan: foto ${props.refLabel || 'awal'}`);

function lockScroll() {
  if (isScrollLocked) return;
  previousHtmlOverflow = document.documentElement.style.overflow;
  previousBodyOverflow = document.body.style.overflow;
  document.documentElement.style.overflow = 'hidden';
  document.body.style.overflow = 'hidden';
  isScrollLocked = true;
}

function unlockScroll() {
  if (!isScrollLocked) return;
  document.documentElement.style.overflow = previousHtmlOverflow;
  document.body.style.overflow = previousBodyOverflow;
  isScrollLocked = false;
}

function stopStream() {
  isTorchOn.value = false;
  supportsTorch.value = false;
  if (activeStream) {
    activeStream.getTracks().forEach((track) => track.stop());
    activeStream = null;
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null;
  }
}

function revokeCapturedPreview() {
  if (capturedPreviewUrl.value) {
    URL.revokeObjectURL(capturedPreviewUrl.value);
    capturedPreviewUrl.value = '';
  }
}

function mapCameraError(err: unknown): string {
  const name = err instanceof Error ? err.name : (err as { name?: string })?.name || '';
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return 'Izin kamera ditolak. Izinkan kamera di pengaturan browser, atau pakai kamera bawaan.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return 'Kamera tidak ditemukan.';
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'Kamera sedang dipakai aplikasi lain.';
  }
  return 'Kamera tidak dapat dibuka. Pakai kamera bawaan ponsel.';
}

async function detectMultipleCameras() {
  try {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoInputs = devices.filter((d) => d.kind === 'videoinput');
    hasMultipleCameras.value = videoInputs.length > 1;
  } catch {
    hasMultipleCameras.value = false;
  }
}

async function requestStreamWithFallback(): Promise<MediaStream> {
  const idealConstraints: MediaStreamConstraints = {
    video: {
      facingMode: { ideal: facingMode.value },
      width: { ideal: 1920 },
      height: { ideal: 1440 },
    },
    audio: false,
  };

  try {
    return await navigator.mediaDevices.getUserMedia(idealConstraints);
  } catch (err) {
    const name = err instanceof Error ? err.name : (err as { name?: string })?.name || '';
    if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
      return await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode.value } },
        audio: false,
      });
    }
    throw err;
  }
}

async function startCamera() {
  stopStream();
  isPreparing.value = true;
  cameraError.value = '';
  captureError.value = '';

  if (!navigator.mediaDevices?.getUserMedia) {
    cameraError.value = 'Kamera langsung tidak tersedia di browser ini.';
    isPreparing.value = false;
    return;
  }

  try {
    const stream = await requestStreamWithFallback();
    if (isUnmounted) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    activeStream = stream;
    const primaryTrack =
      typeof stream.getVideoTracks === 'function' ? stream.getVideoTracks()[0] : undefined;
    const caps =
      primaryTrack && typeof primaryTrack.getCapabilities === 'function'
        ? (primaryTrack.getCapabilities() as { torch?: boolean })
        : null;
    supportsTorch.value = Boolean(caps?.torch);
    isTorchOn.value = false;

    if (videoRef.value) {
      videoRef.value.srcObject = stream;
    }
    await detectMultipleCameras();
  } catch (err) {
    cameraError.value = mapCameraError(err);
    isPreparing.value = false;
  }
}

function handleLoadedMetadata() {
  isPreparing.value = false;
}

function handleVisibilityChange() {
  if (document.visibilityState === 'hidden') {
    stopStream();
  } else if (
    document.visibilityState === 'visible' &&
    !capturedFile.value &&
    !cameraError.value
  ) {
    void startCamera();
  }
}

function handleFlipCamera() {
  facingMode.value = facingMode.value === 'environment' ? 'user' : 'environment';
  void startCamera();
}

async function handleToggleTorch() {
  const track =
    activeStream && typeof activeStream.getVideoTracks === 'function'
      ? activeStream.getVideoTracks()[0]
      : undefined;
  if (!track || !supportsTorch.value || typeof track.applyConstraints !== 'function') return;
  const next = !isTorchOn.value;
  try {
    await track.applyConstraints({
      advanced: [{ torch: next } as MediaTrackConstraintSet],
    });
    isTorchOn.value = next;
  } catch {
    // Abaikan bila perangkat menolak perubahan torch
  }
}

function handleTakeSnapshot() {
  const video = videoRef.value;
  if (!video || isPreparing.value || cameraError.value) return;

  captureError.value = '';
  const width = video.videoWidth || 1280;
  const height = video.videoHeight || 720;
  const stageRect = video.getBoundingClientRect();
  const { sx, sy, sw, sh } = computeCoverCropRect(
    width,
    height,
    stageRect.width,
    stageRect.height,
  );

  const canvas = document.createElement('canvas');
  canvas.width = sw;
  canvas.height = sh;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    captureError.value = 'Gagal mengambil foto. Coba lagi.';
    return;
  }

  // Gambar hanya area frame video yang tampil di layar (tanpa elemen bayangan)
  ctx.drawImage(video, sx, sy, sw, sh, 0, 0, sw, sh);

  canvas.toBlob(
    (blob) => {
      if (!blob) {
        captureError.value = 'Gagal mengambil foto. Coba lagi.';
        return;
      }
      revokeCapturedPreview();
      const file = new File([blob], `kamera-${Date.now()}.jpg`, { type: 'image/jpeg' });
      capturedFile.value = file;
      capturedPreviewUrl.value = URL.createObjectURL(blob);
    },
    'image/jpeg',
    0.92,
  );
}

function handleRetake() {
  revokeCapturedPreview();
  capturedFile.value = null;
  captureError.value = '';
}

function handleConfirmCapture() {
  if (!capturedFile.value) return;
  const file = capturedFile.value;
  stopStream();
  revokeCapturedPreview();
  capturedFile.value = null;
  unlockScroll();
  emit('capture', file);
}

function handleCancel() {
  stopStream();
  revokeCapturedPreview();
  capturedFile.value = null;
  unlockScroll();
  emit('cancel');
}

function handleFallback() {
  const reason = cameraError.value || 'Menggunakan kamera bawaan ponsel.';
  stopStream();
  revokeCapturedPreview();
  capturedFile.value = null;
  unlockScroll();
  emit('fallback', reason);
}

onMounted(() => {
  lockScroll();
  document.addEventListener('visibilitychange', handleVisibilityChange);
  void startCamera();
});

onBeforeUnmount(() => {
  isUnmounted = true;
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  stopStream();
  revokeCapturedPreview();
  unlockScroll();
});
</script>

<template>
  <Teleport to="body">
    <div
      class="cam-root"
      role="dialog"
      aria-modal="true"
      aria-label="Kamera langsung untuk mengambil foto luka"
    >
      <div class="cam-topbar">
        <p class="cam-instruction">
          Cocokkan posisi kaki atau tangan dengan bayangan, lalu tekan tombol bulat.
        </p>
        <div class="cam-top-actions">
          <span v-if="hasRefImage && !capturedFile" class="cam-shadow-label">
            {{ shadowBadgeText }}
          </span>
          <div v-if="!capturedFile && !cameraError" class="cam-top-btns">
            <button
              v-if="supportsTorch"
              id="cam-torch"
              type="button"
              class="cam-chip-btn"
              :aria-pressed="isTorchOn"
              :aria-label="
                isTorchOn ? 'Matikan lampu senter kamera' : 'Nyalakan lampu senter kamera'
              "
              @click="handleToggleTorch"
            >
              {{ isTorchOn ? 'Senter: Nyala' : 'Senter' }}
            </button>
            <button
              id="cam-grid-toggle"
              type="button"
              class="cam-chip-btn"
              :aria-pressed="showGrid"
              :aria-label="
                showGrid
                  ? 'Sembunyikan garis bantu tiga kali tiga'
                  : 'Tampilkan garis bantu tiga kali tiga'
              "
              @click="showGrid = !showGrid"
            >
              {{ showGrid ? 'Matikan garis' : 'Garis 3×3' }}
            </button>
          </div>
        </div>
      </div>

      <div class="cam-stage">
        <template v-if="cameraError">
          <div class="cam-error-box" role="alert">
            <p class="cam-error-msg">{{ cameraError }}</p>
            <button
              id="cam-fallback-btn"
              type="button"
              class="cam-btn cam-btn-primary"
              @click="handleFallback"
            >
              Pakai kamera bawaan
            </button>
          </div>
        </template>

        <template v-else-if="capturedFile && capturedPreviewUrl">
          <img
            :src="capturedPreviewUrl"
            alt="Pratinjau foto hasil kamera"
            class="cam-captured-img"
          />
        </template>

        <template v-else>
          <video
            ref="videoRef"
            class="cam-video"
            autoplay
            playsinline
            muted
            @loadedmetadata="handleLoadedMetadata"
          ></video>

          <img
            v-if="hasRefImage && refImageUrl"
            :src="refImageUrl"
            alt=""
            aria-hidden="true"
            class="cam-shadow-img"
            :style="{ opacity: effectiveShadowOpacity }"
          />

          <div v-if="showGrid" class="cam-grid" aria-hidden="true">
            <span class="cam-grid-v cam-grid-v1"></span>
            <span class="cam-grid-v cam-grid-v2"></span>
            <span class="cam-grid-h cam-grid-h1"></span>
            <span class="cam-grid-h cam-grid-h2"></span>
          </div>

          <div v-if="isPreparing" class="cam-loading" role="status">
            Menyiapkan kamera...
          </div>

          <div v-if="hasRefImage" class="cam-shadow-ctl">
            <label class="cam-slider-wrap" for="cam-opacity">
              <span>Transparansi</span>
              <input
                id="cam-opacity"
                v-model.number="shadowOpacity"
                type="range"
                :min="GHOST_OPACITY_MIN"
                :max="GHOST_OPACITY_MAX"
                :step="GHOST_OPACITY_STEP"
                aria-label="Transparansi bayangan foto awal"
              />
              <output>{{ isShadowHidden ? 0 : shadowOpacity }}%</output>
            </label>

            <button
              id="cam-toggle-shadow"
              type="button"
              class="cam-chip-btn"
              @click="isShadowHidden = !isShadowHidden"
            >
              {{ isShadowHidden ? 'Tampilkan bayangan' : 'Sembunyikan bayangan' }}
            </button>
          </div>
        </template>

        <p v-if="captureError" class="cam-capture-err" role="alert">{{ captureError }}</p>
      </div>

      <div class="cam-controls">
        <template v-if="capturedFile">
          <button
            id="cam-retake"
            type="button"
            class="cam-btn cam-btn-left"
            @click="handleRetake"
          >
            Ulangi
          </button>
          <span class="cam-spacer" aria-hidden="true"></span>
          <button
            id="cam-use-photo"
            type="button"
            class="cam-btn cam-btn-primary cam-btn-right"
            @click="handleConfirmCapture"
          >
            Pakai foto ini
          </button>
        </template>

        <template v-else>
          <button
            id="cam-cancel"
            type="button"
            class="cam-btn cam-btn-left"
            @click="handleCancel"
          >
            Batal
          </button>

          <button
            v-if="!cameraError"
            id="cam-shutter"
            type="button"
            class="cam-shutter"
            aria-label="Ambil foto"
            :disabled="isPreparing"
            @click="handleTakeSnapshot"
          ></button>
          <span v-else class="cam-spacer" aria-hidden="true"></span>

          <button
            v-if="hasMultipleCameras && !cameraError"
            id="cam-flip"
            type="button"
            class="cam-btn cam-btn-right"
            aria-label="Balik kamera"
            @click="handleFlipCamera"
          >
            Balik kamera
          </button>
          <span v-else class="cam-spacer" aria-hidden="true"></span>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style src="@/assets/h3_unggah.css"></style>
