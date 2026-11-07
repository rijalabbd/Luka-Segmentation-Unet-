<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const N = 4
const STEP_MS = 4200

const idx = ref(0)
const isNoAnim = ref(false)
const hoverPaused = ref(false)
const motionReduced = ref(false)
const stepKey = ref(0)

const rootRef = ref<HTMLElement | null>(null)
const trackRef = ref<HTMLElement | null>(null)

let timer: ReturnType<typeof setTimeout> | null = null

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

const cur = computed(() => idx.value % N)
const isRunning = computed(() => !motionReduced.value && !hoverPaused.value)

function schedule() {
  if (timer) clearTimeout(timer)
  if (isRunning.value) {
    timer = setTimeout(() => {
      next()
    }, STEP_MS)
  }
}

function go(n: number, animate = true) {
  isNoAnim.value = !animate
  idx.value = n
  stepKey.value++
  schedule()
}

function next() {
  if (idx.value === N - 1) {
    // Geser ke klon slide 1 (index N = 4), lalu reset diam-diam ke slide 1 asli (index 0)
    idx.value = N
    isNoAnim.value = false
    stepKey.value++

    const onTransitionEnd = () => {
      trackRef.value?.removeEventListener('transitionend', onTransitionEnd)
      if (idx.value === N) {
        go(0, false)
      }
    }

    if (prefersReducedMotion() || !trackRef.value) {
      go(0, false)
    } else {
      trackRef.value.addEventListener('transitionend', onTransitionEnd)
    }
    return
  }
  go(idx.value + 1)
}

function onMouseEnter() {
  hoverPaused.value = true
  schedule()
}

function onMouseLeave() {
  hoverPaused.value = false
  go(idx.value % N, false)
}

function onFocusIn() {
  hoverPaused.value = true
  schedule()
}

function onFocusOut() {
  hoverPaused.value = false
  go(idx.value % N, false)
}

function onVisibilityChange() {
  hoverPaused.value = document.hidden
  if (!document.hidden) {
    go(idx.value % N, false)
  } else {
    schedule()
  }
}

const steps = [
  { num: '01', title: '1 · Foto luka' },
  { num: '02', title: '2 · Segmentasi' },
  { num: '03', title: '3 · Luas & PAC' },
  { num: '04', title: '4 · Narasi' },
]

onMounted(() => {
  if (prefersReducedMotion()) {
    motionReduced.value = true
  }
  document.addEventListener('visibilitychange', onVisibilityChange)
  go(0, false)
})

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div
    id="carousel"
    ref="rootRef"
    class="record"
    :class="{ paused: !isRunning }"
    role="group"
    aria-roledescription="carousel"
    aria-label="Alur pemantauan luka dalam empat langkah"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
    @focusin="onFocusIn"
    @focusout="onFocusOut"
  >
    <div class="record-top">
      <div>
        <div class="record-title">Alur satu kunjungan</div>
        <div class="record-caption">Dari foto luka sampai narasi perkembangan</div>
      </div>
      <span class="record-tag">Pratinjau visual</span>
    </div>

    <div class="viewport">
      <div
        id="track"
        ref="trackRef"
        class="track"
        :class="{ 'no-anim': isNoAnim }"
        :style="{ transform: `translateX(-${idx * 100}%)` }"
      >
        <!-- 1 Foto -->
        <section class="slide" :class="{ active: idx === 0 || idx === N }" aria-label="Langkah 1 dari 4">
          <div class="slide-head">
            <span class="slide-num" aria-hidden="true">01</span>
            <span class="slide-title">Foto luka</span>
            <span class="slide-sub">Satu foto per kunjungan</span>
          </div>
          <div class="image-box" role="img" aria-label="Ilustrasi foto luka asli">
            <div class="skin-form"><div class="wound"></div></div>
            <i class="corner tl" aria-hidden="true"></i>
            <i class="corner tr" aria-hidden="true"></i>
            <i class="corner bl" aria-hidden="true"></i>
            <i class="corner br" aria-hidden="true"></i>
            <span class="chip">Foto asli · jarak &amp; sudut konsisten</span>
          </div>
        </section>

        <!-- 2 Segmentasi -->
        <section class="slide" :class="{ active: idx === 1 }" aria-label="Langkah 2 dari 4">
          <div class="slide-head">
            <span class="slide-num" aria-hidden="true">02</span>
            <span class="slide-title">Segmentasi otomatis</span>
            <span class="slide-sub">U-Net + ResNet-34</span>
          </div>
          <div class="image-box s-seg" role="img" aria-label="Ilustrasi area luka ditandai hijau oleh hasil segmentasi">
            <div class="skin-form">
              <div class="wound"></div>
              <div class="mask-overlay"></div>
            </div>
            <span class="scan"></span>
            <span class="chip green">Area luka terdeteksi</span>
          </div>
        </section>

        <!-- 3 Luas & PAC -->
        <section class="slide" :class="{ active: idx === 2 }" aria-label="Langkah 3 dari 4">
          <div class="slide-head">
            <span class="slide-num" aria-hidden="true">03</span>
            <span class="slide-title">Luas relatif dan PAC</span>
            <span class="slide-sub">Dibanding kunjungan awal</span>
          </div>
          <div class="pac-wrap">
            <div class="stat">
              <div class="stat-label">Kunjungan awal (A₀)</div>
              <div class="stat-value">5,00%</div>
            </div>
            <div class="stat">
              <div class="stat-label">Kunjungan ini (Aₜ)</div>
              <div class="stat-value">3,50%</div>
            </div>
            <div class="bars">
              <div class="bar-row">
                <span>A₀</span>
                <span class="bar" style="--w: 100%"><i></i></span>
                <span class="mono-num">5,00%</span>
              </div>
              <div class="bar-row">
                <span>Aₜ</span>
                <span class="bar now" style="--w: 70%"><i></i></span>
                <span class="mono-num">3,50%</span>
              </div>
            </div>
            <div class="pac-result">
              <div>
                <div class="pac-big">PAC +30,0%</div>
                <div class="pac-sub">ΔA −1,50 poin persentase</div>
              </div>
              <span class="trend">Tren Menurun</span>
            </div>
          </div>
        </section>

        <!-- 4 Narasi -->
        <section class="slide" :class="{ active: idx === 3 }" aria-label="Langkah 4 dari 4">
          <div class="slide-head">
            <span class="slide-num" aria-hidden="true">04</span>
            <span class="slide-title">Narasi otomatis</span>
            <span class="slide-sub">Hanya dari angka terukur</span>
          </div>
          <div class="nar-wrap">
            <div class="nar">
              <div class="nar-tag">Catatan klinis</div>
              <p>Area luka terukur menurun dari 5,00% menjadi 3,50% (PAC +30,0%). Pemeriksaan klinis langsung tetap diperlukan.</p>
            </div>
            <div class="nar">
              <div class="nar-tag">Penjelasan untuk pasien</div>
              <p>Area luka terdeteksi lebih kecil dari pemeriksaan sebelumnya. Tetap lanjutkan perawatan sesuai anjuran. Ini estimasi dari foto, bukan diagnosis.</p>
            </div>
          </div>
        </section>

        <!-- Klon slide 1 untuk loop mulus -->
        <section class="slide" :class="{ active: idx === N }" aria-hidden="true">
          <div class="slide-head">
            <span class="slide-num">01</span>
            <span class="slide-title">Foto luka</span>
            <span class="slide-sub">Satu foto per kunjungan</span>
          </div>
          <div class="image-box">
            <div class="skin-form"><div class="wound"></div></div>
            <i class="corner tl"></i>
            <i class="corner tr"></i>
            <i class="corner bl"></i>
            <i class="corner br"></i>
            <span class="chip">Foto asli · jarak &amp; sudut konsisten</span>
          </div>
        </section>
      </div>
    </div>

    <!-- Stepper 4 langkah -->
    <div id="stepper" class="stepper" role="group" aria-label="Pilih langkah">
      <button
        v-for="(st, i) in steps"
        :key="st.num"
        class="st"
        :class="{ done: i < cur, on: i === cur }"
        type="button"
        :aria-current="i === cur ? 'step' : undefined"
        @click="go(i)"
      >
        <span class="st-bar">
          <i v-if="i === cur" :key="`bar-${stepKey}`"></i>
        </span>
        <span class="st-text">{{ st.title }}</span>
      </button>
    </div>

    <div class="record-footer">
      <span class="art-caption">Ilustrasi konseptual · bukan data pasien</span>
    </div>
  </div>
</template>

<style scoped>
.record {
  --step-ms: 4200ms;
  position: relative;
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 14px 38px rgba(15, 41, 66, 0.08);
  border-radius: var(--radius-lg);
  padding: 20px 22px 14px;
  animation: record-in 0.65s var(--ease) 0.15s both;
}

@keyframes record-in {
  from {
    opacity: 0;
    transform: translate(8px, 10px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.record-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.record-title {
  font-size: var(--fs-sm);
  font-weight: 650;
  color: var(--navy);
}

.record-caption {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  margin-top: 2px;
  line-height: 1.4;
}

.record-tag {
  font-size: var(--fs-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--teal);
  background: var(--teal-soft);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
  font-weight: 600;
}

/* ===== Carousel ===== */
.viewport {
  overflow: hidden;
  margin-top: 4px;
}

.track {
  display: flex;
  transition: transform 0.8s var(--ease);
}

.track.no-anim {
  transition: none !important;
}

.slide {
  flex: 0 0 100%;
  min-width: 0;
  padding: 10px 2px 4px;
  height: 232px;
  display: flex;
  flex-direction: column;
}

.slide-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.slide-num {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
  color: var(--teal);
  line-height: 1;
}

.slide-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--navy);
  letter-spacing: -0.01em;
}

.slide-sub {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  margin-left: auto;
  text-align: right;
}

/* Gambar luka */
.image-box {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, #d6c4b2, #b99e89 52%, #d9c6b6);
  border-radius: var(--radius);
  border: 1px solid var(--border);
}

.skin-form {
  width: 56%;
  height: 82%;
  background: linear-gradient(135deg, #d6b59d, #b68d76 55%, #d4b19b);
  border-radius: 44% 48% 40% 42%;
  transform: rotate(-12deg);
  box-shadow:
    inset -14px -10px 25px rgba(95, 57, 42, 0.14),
    inset 9px 9px 20px rgba(255, 255, 255, 0.24);
  position: relative;
}

.wound {
  position: absolute;
  width: 38%;
  height: 28%;
  left: 31%;
  top: 38%;
  background: #7e403b;
  border-radius: 42% 55% 38% 60%;
  transform: rotate(17deg);
  box-shadow:
    inset 0 0 0 5px rgba(91, 38, 36, 0.2),
    0 0 0 8px rgba(111, 62, 52, 0.12);
}

.mask-overlay {
  position: absolute;
  width: 38%;
  height: 28%;
  left: 31%;
  top: 38%;
  border-radius: 42% 55% 38% 60%;
  transform: rotate(17deg);
  background: rgba(21, 128, 61, 0.52);
  border: 2px solid #14532d;
  box-shadow: 0 0 0 5px rgba(21, 128, 61, 0.15);
  clip-path: inset(0 100% 0 0);
}

.scan {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 2px;
  background: var(--green);
  box-shadow: 0 0 12px 2px rgba(21, 128, 61, 0.45);
  opacity: 0;
  z-index: 2;
  pointer-events: none;
}

.chip {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: rgba(255, 255, 255, 0.96);
  padding: 5px 9px;
  border-radius: var(--radius-sm);
  font-size: var(--fs-xs);
  color: var(--text);
  font-weight: 600;
  opacity: 0;
  transform: translateY(4px);
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}

.chip.green {
  color: #14532d;
  font-weight: 650;
}

.corner {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(15, 41, 66, 0.6);
  pointer-events: none;
}

.corner.tl {
  top: 10px;
  left: 10px;
  border-right: 0;
  border-bottom: 0;
}
.corner.tr {
  top: 10px;
  right: 10px;
  border-left: 0;
  border-bottom: 0;
}
.corner.bl {
  bottom: 10px;
  left: 10px;
  border-right: 0;
  border-top: 0;
}
.corner.br {
  bottom: 10px;
  right: 10px;
  border-left: 0;
  border-top: 0;
}

.slide.active .chip {
  opacity: 1;
  transform: none;
  transition-delay: 0.5s;
}

.slide.active .s-seg .mask-overlay {
  animation: mask-reveal 1.4s cubic-bezier(0.22, 0.75, 0.25, 1) 0.7s forwards;
}

.slide.active .s-seg .scan {
  animation: scan-line 1.4s cubic-bezier(0.45, 0.05, 0.25, 1) 0.7s both;
}

.slide.active .s-seg .chip {
  transition-delay: 2.1s;
}

@keyframes mask-reveal {
  from {
    clip-path: inset(0 100% 0 0);
  }
  to {
    clip-path: inset(0);
  }
}

@keyframes scan-line {
  0% {
    left: 0;
    opacity: 0;
  }
  10%,
  90% {
    opacity: 1;
  }
  100% {
    left: calc(100% - 2px);
    opacity: 0;
  }
}

/* Slide 3: PAC */
.pac-wrap {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  align-content: start;
}

.stat {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  background: #fafbf9;
}

.stat-label {
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.stat-value {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--navy);
  margin-top: 2px;
}

.bars {
  grid-column: 1 / -1;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  display: grid;
  gap: 6px;
  background: var(--surface);
}

.bar-row {
  display: grid;
  grid-template-columns: 68px 1fr 42px;
  gap: 8px;
  align-items: center;
  font-size: var(--fs-xs);
  color: var(--text-muted);
}

.mono-num {
  font-family: var(--mono);
  font-weight: 600;
}

.bar {
  height: 8px;
  background: var(--band);
  border-radius: 999px;
  position: relative;
  overflow: hidden;
}

.bar i {
  position: absolute;
  inset: 0 auto 0 0;
  width: 0;
  background: #8aa59c;
  border-radius: 999px;
  transition: width 1s var(--ease) 0.5s;
}

.bar.now i {
  background: var(--green);
  transition-delay: 0.9s;
}

.slide.active .bar i {
  width: var(--w);
}

.pac-result {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--green);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  background: var(--surface);
  opacity: 0;
  transform: translateY(8px);
  transition:
    opacity 0.5s ease 1.6s,
    transform 0.5s var(--ease) 1.6s;
}

.slide.active .pac-result {
  opacity: 1;
  transform: none;
}

.pac-big {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
  color: var(--green);
  letter-spacing: -0.02em;
  line-height: 1;
}

.pac-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.trend {
  font-size: 11.5px;
  font-weight: 700;
  color: #fff;
  background: var(--green);
  padding: 5px 9px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

/* Slide 4: Narasi */
.nar-wrap {
  flex: 1;
  display: grid;
  gap: 8px;
  align-content: start;
}

.nar {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  background: var(--surface);
  opacity: 0;
  transform: translateX(18px);
  transition:
    opacity 0.5s ease,
    transform 0.6s var(--ease);
}

.slide.active .nar {
  opacity: 1;
  transform: none;
}

.slide.active .nar:nth-child(1) {
  transition-delay: 0.5s;
}
.slide.active .nar:nth-child(2) {
  transition-delay: 1.1s;
}

.nar-tag {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--teal);
  margin-bottom: 4px;
}

.nar p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--text-2);
}

/* ===== Stepper ===== */
.stepper {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 8px;
}

.st {
  background: none;
  border: 0;
  padding: 0;
  text-align: left;
  font: inherit;
  cursor: pointer;
  color: var(--text-muted);
  transition: color var(--dur);
}

.st-bar {
  display: block;
  height: 3px;
  background: var(--border);
  border-radius: 2px;
  position: relative;
  overflow: hidden;
}

.st.done .st-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--teal);
}

.st.on .st-bar i {
  position: absolute;
  inset: 0;
  background: var(--teal);
  transform-origin: left;
  animation: fill var(--step-ms) linear forwards;
}

.paused .st.on .st-bar i {
  animation-play-state: paused;
}

@keyframes fill {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

.st-text {
  display: block;
  font-size: 11.5px;
  margin-top: 5px;
  line-height: 1.25;
  padding: 2px 0;
}

.st.on {
  color: var(--navy);
  font-weight: 650;
}

.record-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}

.art-caption {
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

@media (max-width: 600px) {
  .record {
    padding: 16px 14px 14px;
  }
  .slide {
    height: 250px;
  }
  .slide-sub {
    display: none;
  }
  .st-text {
    font-size: 11px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .track {
    transition-duration: 0.01ms !important;
  }
  .mask-overlay {
    clip-path: inset(0) !important;
  }
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-delay: 0s !important;
    transition-delay: 0s !important;
  }
}
</style>
