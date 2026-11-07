<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import HeroFlow from '@/components/HeroFlow.vue'

const menuOpen = ref(false)
const rootEl = ref<HTMLElement | null>(null)

let observer: IntersectionObserver | null = null

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && menuOpen.value) {
    menuOpen.value = false
  }
}

onMounted(() => {
  document.title = 'Beranda · Dokumentasi Luka'
  document.addEventListener('keydown', handleKeydown)

  const targets = rootEl.value?.querySelectorAll('.reveal, .step-grid') ?? []
  if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('is-visible'))
    return
  }

  observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          obs.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.2 },
  )
  targets.forEach((el) => observer?.observe(el))
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  observer?.disconnect()
})
</script>

<template>
  <div ref="rootEl" class="h1-page">
    <a class="skip-link" href="#konten">Lewati ke konten utama</a>

    <header class="site-header">
      <div class="wrap nav">
        <a class="brand" href="#konten" aria-label="Dokumentasi Luka, ke awal halaman">
          <span class="brand-mark" aria-hidden="true">+</span>
          <span>
            <span class="brand-name">Dokumentasi Luka</span>
            <span class="brand-sub">Pemantauan Berkala</span>
          </span>
        </a>

        <button
          class="menu-btn"
          type="button"
          :aria-expanded="menuOpen"
          aria-controls="navMenu"
          @click="toggleMenu"
        >
          Menu
        </button>

        <nav id="navMenu" class="nav-right" :class="{ open: menuOpen }" aria-label="Navigasi utama">
          <a class="nav-link active" href="#konten" aria-current="page" @click="closeMenu">Beranda</a>
          <a class="nav-link" href="#alur" @click="closeMenu">Alur penggunaan</a>
          <a class="nav-link" href="#batasan" @click="closeMenu">Batasan &amp; privasi</a>
          <RouterLink class="btn" to="/pemeriksaan" @click="closeMenu">Mulai pemeriksaan</RouterLink>
        </nav>
      </div>
    </header>

    <main id="konten">
      <!-- HERO -->
      <section class="wrap hero" aria-labelledby="judul">
        <div>
          <h1 id="judul" class="hero-in">
            Melihat perubahan luka, lebih jelas dari satu kunjungan ke kunjungan berikutnya.
          </h1>
          <p class="hero-copy hero-in">
            Unggah foto luka, tinjau area yang ditandai model segmentasi, lalu bandingkan luas
            relatifnya terhadap kunjungan awal pasien.
          </p>
          <div class="hero-actions hero-in">
            <RouterLink class="btn" to="/pemeriksaan">
              Mulai pemeriksaan <span class="arrow" aria-hidden="true">→</span>
            </RouterLink>
            <a class="text-link" href="#alur">Pelajari alurnya</a>
          </div>
          <div class="hero-note hero-in">
            <span class="note-line" aria-hidden="true"></span>
            <span>
              Alat bantu dokumentasi dan pemantauan visual. Hasil sistem tetap perlu ditinjau oleh
              tenaga kesehatan dan bukan diagnosis.
            </span>
          </div>
        </div>

        <div class="hero-art">
          <div class="art-backdrop" aria-hidden="true"></div>
          <HeroFlow />
        </div>
      </section>

      <!-- ALUR -->
      <section id="alur" class="section" aria-labelledby="t-alur">
        <div class="wrap pad">
          <div class="section-head">
            <h2 id="t-alur" class="section-title">Tiga langkah dalam satu alur kerja.</h2>
            <p class="section-intro">
              Proses dibuat ringkas agar tenaga medis dapat berfokus pada dokumentasi dan
              peninjauan hasil.
            </p>
          </div>
          <div class="step-grid">
            <article class="step reveal">
              <div class="step-num" aria-hidden="true">01</div>
              <h3>Pilih pasien</h3>
              <p>
                Pilih pasien yang sudah terdaftar atau masukkan data pasien baru sebelum memulai
                pemeriksaan.
              </p>
            </article>
            <article class="step reveal">
              <div class="step-num" aria-hidden="true">02</div>
              <h3>Unggah foto</h3>
              <p>
                Masukkan foto luka sesuai panduan pengambilan citra, beserta tanggal kunjungan
                pasien.
              </p>
            </article>
            <article class="step reveal">
              <div class="step-num" aria-hidden="true">03</div>
              <h3>Tinjau hasil</h3>
              <p>
                Periksa hasil segmentasi, estimasi luas relatif luka, dan perubahannya terhadap
                kunjungan awal.
              </p>
            </article>
          </div>
        </div>
      </section>

      <!-- FOTO DIDUKUNG -->
      <section class="section band" aria-labelledby="t-foto">
        <div class="wrap pad">
          <div class="section-head stacked">
            <h2 id="t-foto" class="section-title">Foto seperti apa yang dapat diproses.</h2>
            <p class="section-intro">
              Kualitas foto memengaruhi hasil segmentasi. Foto di luar kondisi berikut sebaiknya
              diambil ulang.
            </p>
          </div>
          <div class="support-grid">
            <div class="support ok">
              <h3><span class="badge" aria-hidden="true">✓</span>Didukung</h3>
              <ul>
                <li>Luka tampak jelas dan berada di tengah bingkai.</li>
                <li>Kamera tegak lurus terhadap permukaan luka.</li>
                <li>Pencahayaan merata tanpa bayangan tajam.</li>
                <li>Foto asli tanpa filter atau pengolahan.</li>
              </ul>
            </div>
            <div class="support no">
              <h3><span class="badge" aria-hidden="true">✕</span>Tidak didukung</h3>
              <ul>
                <li>Foto kabur atau buram.</li>
                <li>Sudut miring ekstrem terhadap permukaan luka.</li>
                <li>Luka tertutup perban, kain, atau cairan.</li>
                <li>Pantulan cahaya berlebih atau foto terlalu gelap.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- PANDUAN -->
      <section class="section" aria-labelledby="t-panduan">
        <div class="wrap pad">
          <div class="section-head">
            <h2 id="t-panduan" class="section-title">
              Foto yang konsisten membantu pemantauan yang lebih bermakna.
            </h2>
            <p class="section-intro">
              Karena pemotretan bersifat non-kontak dan tanpa stiker kalibrasi, perbedaan jarak,
              sudut, dan cahaya antarkunjungan memengaruhi perbandingan luas relatif.
            </p>
          </div>
          <div class="guide-list">
            <article class="guide-item reveal">
              <svg
                class="guide-ico"
                viewBox="0 0 34 34"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                aria-hidden="true"
              >
                <circle cx="17" cy="24" r="3" />
                <g class="g-dist"><path d="M5 8h24M5 5v6M29 5v6" /></g>
              </svg>
              <div class="guide-num">01 / JARAK</div>
              <h3>Jaga jarak tetap konsisten</h3>
              <p>
                Gunakan jarak yang sama pada setiap kunjungan (misalnya dengan tali atau penggaris
                pengatur jarak) dan jangan memakai zoom digital.
              </p>
            </article>
            <article class="guide-item reveal">
              <svg
                class="guide-ico"
                viewBox="0 0 34 34"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                aria-hidden="true"
              >
                <path d="M4 28h26" />
                <g class="g-angle">
                  <rect x="12" y="6" width="10" height="14" rx="2" />
                  <path d="M17 20v8" />
                </g>
              </svg>
              <div class="guide-num">02 / SUDUT</div>
              <h3>Posisikan kamera tegak lurus</h3>
              <p>Arahkan kamera 90° terhadap permukaan area luka.</p>
            </article>
            <article class="guide-item reveal">
              <svg
                class="guide-ico"
                viewBox="0 0 34 34"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                aria-hidden="true"
              >
                <g class="g-light">
                  <circle cx="17" cy="17" r="5" />
                  <path
                    d="M17 4v4M17 26v4M4 17h4M26 17h4M8 8l3 3M23 23l3 3M26 8l-3 3M11 23l-3 3"
                  />
                </g>
              </svg>
              <div class="guide-num">03 / CAHAYA</div>
              <h3>Pastikan cahaya memadai</h3>
              <p>Hindari bayangan tajam dan pantulan cahaya berlebih.</p>
            </article>
            <article class="guide-item reveal">
              <svg
                class="guide-ico"
                viewBox="0 0 34 34"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                aria-hidden="true"
              >
                <rect x="5" y="7" width="24" height="20" rx="2" />
                <circle cx="14" cy="15" r="3" />
                <rect
                  class="g-filter"
                  x="17"
                  y="7"
                  width="12"
                  height="20"
                  fill="currentColor"
                  opacity=".12"
                  stroke="none"
                />
              </svg>
              <div class="guide-num">04 / CITRA</div>
              <h3>Gunakan foto tanpa filter</h3>
              <p>Hindari filter atau pengolahan yang mengubah tampilan luka.</p>
            </article>
          </div>
        </div>
      </section>

      <!-- BATASAN & PRIVASI -->
      <section id="batasan" class="section band" aria-labelledby="t-batasan">
        <div class="wrap pad">
          <div class="section-head stacked">
            <h2 id="t-batasan" class="section-title">Yang dilakukan sistem, dan yang tidak.</h2>
          </div>
          <div class="info-grid">
            <div class="info">
              <h3>Batasan sistem</h3>
              <p>
                Sistem menandai area luka pada foto (segmentasi) dan menghitung
                <strong>luas relatif</strong> sebagai persentase terhadap seluruh citra, lalu
                membandingkannya antarkunjungan.
              </p>
              <ul>
                <li>Bukan alat diagnosis dan tidak menilai jenis atau tingkat keparahan luka.</li>
                <li>Bukan ukuran fisik (cm²), karena tidak memakai stiker atau penggaris kalibrasi.</li>
                <li>Hasil perlu ditinjau dan dikonfirmasi oleh tenaga kesehatan.</li>
              </ul>
            </div>
            <div class="info">
              <h3>Persetujuan dan data pasien</h3>
              <p>
                <strong>Persetujuan pasien (informed consent)</strong> harus diperoleh sebelum luka
                difoto. Jelaskan tujuan pemotretan dan bagaimana foto akan digunakan.
              </p>
              <p>
                Data identitas pasien tetap tersimpan di server lokal fasilitas kesehatan dan tidak
                dikirim ke layanan luar.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section class="wrap final-cta" aria-labelledby="t-cta">
        <div>
          <h2 id="t-cta">Mulai dokumentasi pemeriksaan pasien.</h2>
          <p>Pilih pasien untuk memulai kunjungan dan mengunggah foto luka.</p>
        </div>
        <RouterLink class="btn" to="/pemeriksaan">Mulai pemeriksaan</RouterLink>
      </section>
    </main>

    <footer class="site-footer">
      <div class="wrap footer-inner">
        <div class="footer-brand">Dokumentasi Luka <span>· Pemantauan berkala</span></div>
        <div class="footer-note">Alat bantu dokumentasi visual, bukan pengganti penilaian klinis.</div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.h1-page {
  min-height: 100dvh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: var(--fs-lg);
}

a {
  color: inherit;
  text-decoration: none;
}

.wrap {
  width: min(1120px, calc(100% - 48px));
  margin: auto;
}

h1,
h2,
h3,
p {
  margin: 0;
}

:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
  border-radius: 3px;
}

.skip-link {
  position: absolute;
  left: 16px;
  top: -80px;
  z-index: 100;
  background: var(--navy);
  color: #fff;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  border-radius: var(--radius);
  transition: top var(--dur);
}

.skip-link:focus {
  top: 10px;
}

/* Unified Header matching H2–H5 */
.site-header {
  position: relative;
  min-height: 64px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.nav {
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 32px;
  height: 32px;
  border: 1.5px solid var(--navy);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--navy);
  font-weight: 600;
  font-size: 18px;
  line-height: 1;
  flex: none;
}

.brand-name {
  display: block;
  font-size: 16px;
  font-weight: 650;
  color: var(--navy);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.brand-sub {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.2;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.nav-link {
  font-size: 14px;
  color: var(--text-2);
  padding: 10px 4px;
  position: relative;
  transition: color var(--dur);
}

.nav-link:hover {
  color: var(--navy);
}

.nav-link.active {
  color: var(--navy);
  font-weight: 650;
}

.nav-link.active::after {
  content: '';
  position: absolute;
  left: 4px;
  right: 4px;
  bottom: 2px;
  height: 2px;
  background: var(--teal);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 20px;
  background: var(--navy);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  border-radius: var(--radius);
  border: 0;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition:
    background-color var(--dur) ease,
    transform var(--dur) ease;
}

.btn:hover {
  background: var(--navy-hover);
}

.btn:hover .arrow {
  transform: translateX(3px);
}

.arrow {
  display: inline-block;
  transition: transform var(--dur);
}

.text-link {
  font-size: 14px;
  font-weight: 600;
  color: var(--teal);
  border-bottom: 1.5px solid var(--teal);
  padding: 10px 0 3px;
  transition:
    color var(--dur),
    border-color var(--dur);
}

.text-link:hover {
  color: var(--navy);
  border-color: var(--navy);
}

.menu-btn {
  display: none;
  min-height: 44px;
  min-width: 44px;
  padding: 0 14px;
  background: var(--surface);
  border: 1.5px solid var(--border-control);
  border-radius: var(--radius);
  font: inherit;
  font-size: 14px;
  font-weight: 650;
  color: var(--navy);
  cursor: pointer;
}

/* Hero */
.hero {
  padding: 64px 0 60px;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 48px;
  align-items: center;
}

h1 {
  font-size: clamp(30px, 3.5vw, 44px);
  line-height: 1.15;
  letter-spacing: -0.03em;
  font-weight: 650;
  color: var(--navy);
  margin: 0 0 18px;
  max-width: 540px;
}

.hero-copy {
  font-size: var(--fs-lg);
  line-height: 1.7;
  color: var(--text-2);
  max-width: 500px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 28px;
  flex-wrap: wrap;
}

.hero-note {
  margin-top: 28px;
  display: flex;
  gap: 12px;
  max-width: 470px;
  color: var(--text-muted);
  font-size: var(--fs-sm);
  line-height: 1.6;
}

.note-line {
  width: 3px;
  border-radius: 2px;
  background: var(--teal);
  flex: none;
}

.hero-in {
  opacity: 0;
  transform: translateY(14px);
  animation: rise 0.65s var(--ease) forwards;
}

.hero-in:nth-child(1) {
  animation-delay: 0.04s;
}
.hero-in:nth-child(2) {
  animation-delay: 0.12s;
}
.hero-in:nth-child(3) {
  animation-delay: 0.22s;
}
.hero-in:nth-child(4) {
  animation-delay: 0.32s;
}
.hero-in:nth-child(5) {
  animation-delay: 0.42s;
}

@keyframes rise {
  to {
    opacity: 1;
    transform: none;
  }
}

.hero-art {
  position: relative;
  width: 100%;
  max-width: 480px;
  margin-left: auto;
}

.art-backdrop {
  position: absolute;
  inset: 10px -10px -10px 10px;
  background: var(--teal-soft);
  border-radius: var(--radius-lg);
  z-index: 0;
}

/* Sections */
.section {
  border-top: 1px solid var(--border);
}

.band {
  background: var(--band);
}

.pad {
  padding: 52px 0 60px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 28px;
  margin-bottom: 28px;
}

.section-head.stacked {
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}

.section-title {
  font-size: 26px;
  line-height: 1.22;
  letter-spacing: -0.025em;
  font-weight: 650;
  color: var(--navy);
  max-width: 520px;
}

.section-intro {
  max-width: 460px;
  color: var(--text-2);
  font-size: var(--fs-md);
  line-height: 1.6;
}

/* Step Grid */
.step-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--border-strong);
  border-bottom: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  overflow: hidden;
}

.step-grid::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  height: 3px;
  width: 0;
  background: var(--teal);
  transition: width 1.1s var(--ease) 0.15s;
}

.step-grid.is-visible::before {
  width: 100%;
}

.step {
  padding: 24px 26px 26px;
}

.step + .step {
  border-left: 1px solid var(--border);
}

.step-num {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
  color: var(--teal);
}

.step h3 {
  font-size: 17px;
  letter-spacing: -0.015em;
  color: var(--navy);
  margin: 12px 0 8px;
  font-weight: 650;
}

.step p {
  font-size: var(--fs-sm);
  line-height: 1.65;
  color: var(--text-2);
}

.reveal {
  opacity: 0;
  transform: translateY(12px);
  transition:
    opacity var(--dur-reveal) ease,
    transform var(--dur-reveal) var(--ease);
}

.reveal.is-visible {
  opacity: 1;
  transform: none;
}

.reveal:nth-child(2) {
  transition-delay: 75ms;
}
.reveal:nth-child(3) {
  transition-delay: 140ms;
}
.reveal:nth-child(4) {
  transition-delay: 200ms;
}

/* Support Grid */
.support-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.support {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top-width: 3px;
  border-radius: var(--radius-lg);
  padding: 24px 26px 26px;
}

.support.ok {
  border-top-color: var(--green);
}

.support.no {
  border-top-color: var(--error);
}

.support h3 {
  font-size: var(--fs-lg);
  font-weight: 650;
  color: var(--navy);
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.badge {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  flex: none;
}

.ok .badge {
  background: var(--green);
}
.no .badge {
  background: var(--error);
}

.support ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.support li {
  font-size: var(--fs-sm);
  line-height: 1.6;
  color: var(--text-2);
  padding-left: 22px;
  position: relative;
}

.support li::before {
  position: absolute;
  left: 0;
  font-weight: 700;
}

.ok li::before {
  content: '✓';
  color: var(--green);
}

.no li::before {
  content: '✕';
  color: var(--error);
}

/* Guide List */
.guide-list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid var(--border-strong);
}

.guide-item {
  padding: 22px 22px 0 0;
}

.guide-item + .guide-item {
  border-left: 1px solid var(--border);
  padding-left: 22px;
}

.guide-ico {
  width: 34px;
  height: 34px;
  margin-bottom: 12px;
  color: var(--teal);
}

.guide-ico * {
  transition:
    transform 0.4s var(--ease),
    opacity 0.4s;
  transform-box: fill-box;
  transform-origin: center;
}

.g-angle {
  transform: rotate(-28deg);
}

.guide-item:hover .g-dist {
  transform: scaleX(1.3);
}
.guide-item:hover .g-angle {
  transform: rotate(0);
}
.guide-item:hover .g-light {
  transform: scale(1.22);
}
.guide-item:hover .g-filter {
  transform: translateX(6px);
  opacity: 0.25;
}

.guide-num {
  font-family: var(--mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.06em;
  color: var(--teal);
  font-weight: 700;
}

.guide-item h3 {
  font-size: var(--fs-md);
  font-weight: 650;
  color: var(--navy);
  margin: 10px 0 6px;
  line-height: 1.35;
}

.guide-item p {
  font-size: var(--fs-sm);
  line-height: 1.6;
  color: var(--text-2);
  max-width: 240px;
}

/* Info Grid */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.info {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 24px 26px 26px;
}

.info h3 {
  font-size: 18px;
  letter-spacing: -0.015em;
  font-weight: 650;
  color: var(--navy);
  margin-bottom: 12px;
}

.info p,
.info li {
  font-size: var(--fs-sm);
  line-height: 1.65;
  color: var(--text-2);
}

.info p + p {
  margin-top: 10px;
}

.info ul {
  margin: 12px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.info strong {
  color: var(--text);
}

/* Final CTA & Footer */
.final-cta {
  padding: 48px 0 52px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 28px;
}

.final-cta h2 {
  font-size: 24px;
  letter-spacing: -0.025em;
  font-weight: 650;
  color: var(--navy);
  margin-bottom: 6px;
}

.final-cta p {
  font-size: var(--fs-sm);
  color: var(--text-muted);
}

.site-footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding: 20px 0 24px;
}

.footer-inner {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}

.footer-brand {
  font-size: var(--fs-sm);
  font-weight: 650;
  color: var(--navy);
}

.footer-brand span {
  font-weight: 400;
  color: var(--text-muted);
}

.footer-note {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  text-align: right;
}

/* Responsive */
@media (max-width: 1000px) {
  .hero {
    grid-template-columns: 1fr;
    gap: 38px;
    padding: 48px 0;
  }
  .hero-art {
    margin: 0 auto;
  }
  .art-backdrop {
    inset: 10px -8px -8px 8px;
  }
  .guide-list {
    grid-template-columns: 1fr 1fr;
    row-gap: 26px;
  }
  .guide-item:nth-child(3) {
    border-left: 0;
    padding-left: 0;
  }
  .section-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}

@media (max-width: 760px) {
  .wrap {
    width: calc(100% - 32px);
  }
  .nav {
    min-height: 64px;
    flex-wrap: wrap;
    padding: 8px 0;
  }
  .brand-sub {
    display: none;
  }
  .menu-btn {
    display: inline-flex;
    align-items: center;
  }
  .nav-right {
    display: none;
    width: 100%;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 8px 0 14px;
    border-top: 1px solid var(--border);
    margin-top: 8px;
  }
  .nav-right.open {
    display: flex;
  }
  .nav-link {
    padding: 13px 2px;
    border-bottom: 1px solid var(--border);
    font-size: var(--fs-md);
  }
  .nav-link.active::after {
    display: none;
  }
  .nav-right .btn {
    margin-top: 14px;
  }
  .hero {
    padding: 36px 0 38px;
  }
  h1 {
    font-size: 32px;
  }
  .hero-copy {
    font-size: var(--fs-md);
  }
  .pad {
    padding: 38px 0 42px;
  }
  .section-title {
    font-size: 22px;
  }
  .step-grid,
  .support-grid,
  .info-grid {
    grid-template-columns: 1fr;
  }
  .step {
    padding: 20px;
  }
  .step + .step {
    border-left: 0;
    border-top: 1px solid var(--border);
  }
  .guide-list {
    grid-template-columns: 1fr;
  }
  .guide-item,
  .guide-item + .guide-item {
    border-left: 0;
    padding-left: 0;
  }
  .guide-item + .guide-item {
    border-top: 1px solid var(--border);
    margin-top: 18px;
  }
  .final-cta,
  .footer-inner {
    flex-direction: column;
    align-items: flex-start;
  }
  .final-cta .btn {
    width: 100%;
  }
  .footer-note {
    text-align: left;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-delay: 0s !important;
    transition-duration: 0.01ms !important;
    transition-delay: 0s !important;
  }
  .hero-in,
  .reveal {
    opacity: 1;
    transform: none;
  }
  .step-grid::before {
    width: 100%;
  }
}
</style>
