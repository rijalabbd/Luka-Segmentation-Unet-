<template>
  <aside id="guide" class="card guide guide-wrap" aria-labelledby="t-guide">
    <h2 id="t-guide">Panduan Pengambilan Foto</h2>
    <p class="sub">Lima prinsip agar foto antarkunjungan dapat dibandingkan.</p>
    <ol>
      <li>
        <span class="num" aria-hidden="true">1</span>
        <div>
          <h3>Jarak konsisten</h3>
          <p>
            Gunakan jarak yang sama pada setiap kunjungan (misalnya dengan tali atau penggaris
            pengatur jarak) dan jangan memakai zoom digital.
          </p>
        </div>
      </li>
      <li>
        <span class="num" aria-hidden="true">2</span>
        <div>
          <h3>Kamera tegak lurus</h3>
          <p>Posisikan kamera 90° terhadap permukaan luka.</p>
        </div>
      </li>
      <li>
        <span class="num" aria-hidden="true">3</span>
        <div>
          <h3>Pencahayaan cukup</h3>
          <p>Hindari bayangan gelap dan pantulan cahaya.</p>
        </div>
      </li>
      <li>
        <span class="num" aria-hidden="true">4</span>
        <div>
          <h3>Tanpa filter</h3>
          <p>Gunakan foto alami tanpa modifikasi warna.</p>
        </div>
      </li>
      <li>
        <span class="num" aria-hidden="true">5</span>
        <div>
          <h3>Sertakan penggaris</h3>
          <p>Bila tersedia, letakkan penggaris di dekat luka dan sebidang dengan permukaannya.</p>
        </div>
      </li>
    </ol>
    <p class="calib">
      <svg
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        stroke-linecap="round"
        aria-hidden="true"
      >
        <circle cx="10" cy="10" r="7.5" />
        <path d="M10 9v5M10 6.2v.1" />
      </svg>
      <span>
        <strong>Catatan:</strong> Luas dihitung relatif terhadap citra. Jika foto memuat penggaris
        sebidang luka, kalibrasi opsional tersedia di halaman hasil.
      </span>
    </p>
  </aside>
</template>

<style scoped>
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 22px 24px;
}
.guide h2 {
  font-size: 16px;
  font-weight: 650;
  color: var(--navy);
  margin: 0 0 4px;
}
.guide .sub {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 14px;
}
.guide ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 14px;
}
.guide li {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
}
.num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--teal-soft);
  color: var(--teal);
  font-weight: 700;
  font-size: 13px;
  display: grid;
  place-items: center;
}
.guide h3 {
  font-size: 14px;
  font-weight: 650;
  margin: 0;
}
.guide li p {
  font-size: 13px;
  color: var(--text-2);
  margin: 2px 0 0;
}
.calib {
  margin: 18px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-2);
}
.calib svg {
  width: 18px;
  height: 18px;
  color: var(--teal);
  margin-top: 1px;
}
@media (max-width: 640px) {
  .card {
    padding: 18px 16px;
  }
}
</style>
