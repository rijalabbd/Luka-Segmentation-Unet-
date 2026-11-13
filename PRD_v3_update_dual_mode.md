# PRD WoundAI v3: Update Dual-Mode (Jarak Kamera)

**Dasar**: proposal terbaru (*pa rijal luka v2*, Bab 1–3) dan ringkasan rancangan dual-mode (revisi masukan Pak Wiratmoko).
**Cara pakai**: dokumen ini adalah addendum untuk PRD v2. Jika bertentangan dengan PRD v2, dokumen ini yang berlaku. Bagian PRD v2 yang tidak disebut di sini tidak berubah.

---

## 0. Keputusan (final, 13 Nov 2026)

Ketiga keputusan di bawah sudah ditetapkan. Nilainya tetap disimpan sebagai konstanta/konfigurasi.

| ID | Keputusan | Dampak ke proposal |
| :--- | :--- | :--- |
| **D1** | Peringatan jarak pada mode non-kalibrasi berlaku untuk **semua \|PAC\| ≥ 5%**: `PAC_WARN_MIN=5`, `PAC_WARN_MAX=None`. Rentang 5–10% memakai teks `DISTANCE_SENSITIVE`; di atas 10% memakai teks yang lebih kuat `DISTANCE_LARGE`. Alasan: pergeseran 20→25 cm menghasilkan PAC semu +36%. | Subbab 3.7.3 (batas atas 10% dihapus), Tabel 3.3 |
| **D2** | Status tren pada mode terkalibrasi memakai **PAC cm² saja** (ambang ±5,0). Kriteria ΔA ±1,0 poin persentase hanya berlaku pada mode relatif. | Catatan kaki Tabel 3.3 |
| **D3** | Pada mode terkalibrasi, A₀, Aₜ, ΔA dikirim ke LLM dalam cm². Lima angka tetap, ditambah satu string satuan (`"%"` atau `"cm²"`). String satuan bukan identitas pasien. | Subbab 3.8.2, kasus K10 |

---

## 1. Perubahan Sumber Kebenaran dan Scope (PRD v2, Bagian 1)

1. Sumber kebenaran: *pa rijal luka v2* (bukan "Pa Rijal Segmentasi Kusta" versi lama).
2. **Hapus** dari "Di luar scope": *"pengukuran cm²"*. Kalibrasi penggaris dua titik (opsional) kini masuk scope.
3. Tetap di luar scope: deteksi otomatis penggaris atau stiker, sensor depth, koreksi sudut pandang 3D, registrasi citra otomatis (OpenCV gagal pada 15 dari 17 pasangan), kamera langsung (live camera). Semuanya dicatat sebagai pengembangan lanjutan.
4. Evaluasi SK-1 sampai SK-2d tetap dikerjakan lewat skrip terpisah. Backend wajib menyediakan endpoint kalibrasi yang bisa dipanggil lewat skrip (titik dan panjang sebagai parameter) agar SK-2d bisa memakainya.
5. Perbaiki rujukan nomor di PRD v2:
   - Gambar H3 = **3.9**, H4 = **3.10**, H5 = **3.11** (sebelumnya 3.8, 3.9, 3.10).
   - Kasus uji SK-3: jangan rujuk "Tabel 3.8". Gunakan sebutan "tabel kasus uji K1–K10" (penomoran tabel di proposal sedang dirapikan).

## 2. Aturan Global Tambahan (PRD v2, Bagian 2)

**G1. Dua mode pengukuran per kunjungan**
- `relative`: luas dalam % citra (bawaan, selalu dihitung dan disimpan).
- `calibrated`: luas dalam cm² jika operator menerapkan kalibrasi dua titik pada draf.

**G2. Rumus kalibrasi** (koordinat dan panjang piksel memakai dimensi citra **asli**, setelah orientasi EXIF diterapkan dan EXIF dibuang)

$$\Delta px = \sqrt{(x_2-x_1)^2 + (y_2-y_1)^2} \qquad s = \frac{L_{cm}}{\Delta px}\ \text{(cm/px)}$$
$$A_{cm^2} = \frac{N_{\text{luka}}}{65.536} \times W \times H \times s^2$$

$W \times H$ adalah dimensi citra asli. Validasi: titik berbeda dan di dalam citra, $\Delta px \ge 2\%$ dari panjang diagonal citra, $0 < L_{cm} \le 50$.

**G3. Aturan anti-campur satuan**
- `area_pct` (relatif) selalu disimpan untuk setiap kunjungan.
- `pac_cm2` dihitung hanya jika A₀ **dan** Aₜ sama-sama terkalibrasi. Selain itu `pac_basis = "relative"` untuk kedua kunjungan.
- Kunjungan `final` tidak bisa dikalibrasi ulang. Jika baseline tidak terkalibrasi, kunjungan lanjutan tetap memakai PAC relatif walaupun foto lanjutannya terkalibrasi. UI menampilkan catatan alasannya.

**G4. Status tren**
- `relative`: aturan Tabel 3.3 tidak berubah (PAC ±5,0 dan ΔA ±1,0 poin persentase).
- `calibrated`: PAC cm² saja dengan ambang ±5,0 (nilai bawaan D2).
- Implementasikan sebagai `classify(pac, delta_rel_pp, basis)` agar D2 mudah diganti.

**G5. Peringatan (dikirim backend sebagai kode, teks dipetakan di frontend)**

| Kode | Kondisi | Teks (id) |
| :--- | :--- | :--- |
| `DISTANCE_SENSITIVE` | `basis == "relative"` dan `5 ≤ \|PAC\| ≤ 10` (D1) | "Perubahan sekecil ini dapat dipengaruhi variasi jarak pemotretan (±1 cm). Jika foto memuat penggaris, gunakan kalibrasi. Konfirmasi dengan pemeriksaan klinis langsung." |
| `DISTANCE_LARGE` | `basis == "relative"` dan `\|PAC\| > 10` (D1) | "Pada foto tanpa kalibrasi, selisih jarak pemotretan dapat menimbulkan perubahan luas semu yang besar (misalnya selisih 5 cm pada jarak 20 cm setara sekitar 36%). Periksa kembali jarak foto dengan overlay, atau gunakan kalibrasi jika ada penggaris." |
| `LOW_BASELINE` | `A₀_rel < 1,0%` | "Luas awal kurang dari 1% dari citra, sehingga PAC sangat sensitif terhadap selisih kecil jumlah piksel." |
| `MIXED_BASIS` | Kunjungan ini terkalibrasi tetapi A₀ tidak | "PAC dihitung dengan luas relatif karena kunjungan awal tidak terkalibrasi." |

**G6. Batasan yang wajib tertulis di UI**: kalibrasi mengoreksi jarak kamera, tidak mengoreksi sudut pandang 3D atau lengkungan anatomi. Segmen penggaris harus dekat dan sebidang dengan permukaan luka.

**G7. Gemini**: nama model dibaca dari env `GEMINI_MODEL` (bawaan `gemini-2.0-flash`). Verifikasi dulu bahwa model ini masih dilayani; jika tidak, ganti lewat env tanpa ubah kode.

**G8. Privasi**: titik kalibrasi, panjang penggaris, dan skala tidak dikirim ke Gemini. Yang dikirim: lima angka, status tren, dan string satuan (D3).

## 3. Perubahan Fase

| Fase | Isi | Status |
| :--- | :--- | :--- |
| 0, 1, 2 | Seperti PRD v2 | Selesai |
| **2b** (baru) | Revisi H3: ghost overlay + perbaikan (Bagian 4) | Belum |
| 3a | Backend konfirmasi/PAC/narasi | Selesai di `fase-3-h4-v2` |
| **3a-2** (baru) | Backend kalibrasi, PAC dua basis, peringatan (Bagian 5) | Belum |
| 3b | Frontend H4 termasuk panel kalibrasi (Bagian 6) | Belum |
| 4, 5 | Penyesuaian kecil (Bagian 8) | Belum |

Urutan: 2b, 3a-2, 3b, 4, 5. Berhenti dan lapor di akhir tiap fase (format laporan PRD v2 Bagian 9).

## 4. Fase 2b: Revisi H3 (Ghost Overlay)

Mengganti dan melengkapi PRD v2 Bagian 10.3.

**Sumber acuan**
- Kunjungan ≥ 2: panel acuan punya dua tab, **"Kunjungan Awal (Baseline)"** (bawaan) dan **"Kunjungan Terakhir"**. Jika kunjungan terakhir adalah baseline, tampilkan satu tab saja. Alasan baseline jadi bawaan: PAC dihitung terhadap A₀, jadi selisih jarak terhadap foto baseline yang menimbulkan bias.
- Kunjungan 1: keterangan *"Kunjungan awal: foto ini akan menjadi acuan kunjungan berikutnya."* dan saran menyertakan penggaris sebidang luka bila ada.

**Ghost overlay**
- Aktif setelah foto baru dipilih (kunjungan ≥ 2). Foto acuan ditumpuk semi-transparan di atas pratinjau pada bingkai yang sama.
- Kontrol: saklar *"Tampilkan overlay foto acuan"* (`role="switch"`, `aria-checked`) dan slider transparansi **0–80%** (bawaan 40%, langkah 5, nilai tampil di sebelah label). Bukan 0–100%.
- Teks bantu: *"Samakan ukuran bagian tubuh yang tidak berubah (misalnya lebar pergelangan atau sisi kaki), bukan tepi luka."*
- Overlay murni visual: tidak mengubah berkas yang diunggah, `pointer-events: none`, dan diatur ulang saat foto diganti.
- Mode berdampingan dari PRD v2 10.3 tetap ada sebagai tampilan alternatif.

**Perbaikan lain (dari audit mockup)**
1. Validasi tipe berkas hanya `image/jpeg` dan `image/png`. Pesan error menyebut "JPG atau PNG" (mockup lama menyebut WebP dan menerima semua `image/*`).
2. Atribut `min` pada input tanggal = tanggal kunjungan `final` terakhir, `max` = hari ini (toleransi satu hari di backend, sesuai 10.2 butir 4).
3. Teks kotak centang kunjungan ≥ 2: *"Saya sudah membandingkan foto dengan foto acuan; jarak dan sudut sudah sama."*
4. Catatan panduan: ganti *"tanpa penanda kalibrasi fisik"* dengan *"Luas dihitung relatif terhadap citra. Jika foto memuat penggaris sebidang luka, kalibrasi opsional tersedia di halaman hasil."* Tambahkan butir panduan ke-5: *"Sertakan penggaris di dekat luka bila tersedia."*
5. Tombol "Gunakan Foto Sampel" hanya untuk mode demo atau pasien `is_demo` (PRD v2 10.2 butir 2).

**Kriteria selesai**: tangkapan layar overlay aktif pada pasien dengan baseline dan kunjungan terakhir berbeda; tes tipe berkas dan tanggal min/max; overlay hilang saat foto diganti.

## 5. Fase 3a-2: Backend Kalibrasi

**Migrasi `visits` (kolom baru, semua nullable kecuali disebut)**

| Kolom | Keterangan |
| :--- | :--- |
| `img_width_px`, `img_height_px` | Dimensi citra asli tersimpan (setelah orientasi EXIF) |
| `calib_x1`, `calib_y1`, `calib_x2`, `calib_y2` | Titik kalibrasi dalam piksel citra asli |
| `calib_length_cm` | Panjang fisik segmen (L) |
| `scale_cm_per_px` | Skala s |
| `area_cm2` | Luas terkalibrasi |
| `pac_rel` | PAC berbasis luas relatif, selalu dihitung pada kunjungan lanjutan |
| `pac_cm2` | PAC berbasis cm², hanya jika G3 terpenuhi |
| `pac_basis` | `relative` atau `calibrated` (menentukan nilai `pac` utama) |
| `warnings` | Daftar kode peringatan G5 (JSON) |

`pac`, `delta_area`, `trend_status` yang sudah ada tetap sebagai nilai utama sesuai `pac_basis`. Simpan `pac_rel` terpisah agar SK-2d bisa membandingkan kedua basis.

**Endpoint baru (prefix `/api/v1`)**

| Method dan Path | Fungsi |
| :--- | :--- |
| `PUT /visits/{id}/calibration` | Body: `x1,y1,x2,y2,length_cm`. Hanya untuk `draft`. Hitung `s` dan `area_cm2`. `422` jika validasi G2 gagal, `409` jika sudah `final` |
| `DELETE /visits/{id}/calibration` | Hapus kalibrasi pada `draft` |

`GET /visits/{id}` untuk `draft` mengembalikan objek `preview` (PAC, ΔA, status, peringatan) yang dihitung saat itu, tidak disimpan, tanpa pemanggilan LLM. Dengan begitu operator melihat efek kalibrasi sebelum konfirmasi. Respons juga memuat dimensi citra asli, data kalibrasi, dan `pac_rel` bila ada.

`confirm` (satu transaksi, urutan PRD v2 Bagian 6) ditambah: tentukan `pac_basis` (G3), hitung PAC, status (G4), dan peringatan (G5) sebelum memanggil narasi.

**Tes wajib (tempelkan output)**
1. Kalibrasi: W×H = 1600×1200, N_luka = 3277, Δpx = 80, L = 2 cm, maka s = 0,025 cm/px dan `area_cm2` ≈ 60,00 (toleransi 0,01).
2. Simulasi jarak: `At_rel = A0_rel × 0,64` memberi `pac_rel` = +36,0. Dengan skala s_t/s_0 = 1,25 pada luka fisik sama, `pac_cm2` = 0,0 (toleransi 0,1) dan status `Tren Stabil`.
3. G3: A₀ tidak terkalibrasi dan Aₜ terkalibrasi memberi `pac_basis = relative` dan peringatan `MIXED_BASIS`.
4. G5: `DISTANCE_SENSITIVE` untuk PAC +5,0 dan +10,0 (batas inklusif) dan untuk −7,0; `DISTANCE_LARGE` untuk +10,1 dan +36,0; tidak ada peringatan jarak untuk +4,9; tidak ada pada basis `calibrated`. `LOW_BASELINE` untuk A₀_rel = 0,8.
5. Validasi `422`: titik sama, titik di luar citra, Δpx terlalu kecil, L ≤ 0 atau > 50.
6. `PUT` pada kunjungan `final` memberi `409`.
7. Tes kasus K4–K7 (PAC 30,0 / 2,0 / −30,0 / batas +5,0) tetap lulus.

## 6. Fase 3b: Frontend H4

Patokan desain: mockup H4 yang diperbarui (Bagian 9). Perilaku:

**Draf** (PRD v2 Bagian 6 diperluas)
- Foto asli dan overlay masker, luas Aₜ, panel **Kalibrasi Penggaris (Opsional)**, **Pratinjau PAC (belum disimpan)** dari objek `preview`. Narasi (tab) **tidak** ditampilkan pada draf; gantikan dengan teks *"Narasi dibuat setelah hasil dikonfirmasi."*
- Panel kalibrasi (tertutup bawaan):
  1. Instruksi: klik dua titik pada garis skala penggaris, sebaiknya garis angka yang jelas (misalnya 1 ke 3 cm), bukan tepi stiker (angka 0). Penggaris harus sebidang dengan luka.
  2. Foto asli ditampilkan besar. Klik menaruh titik 1 lalu titik 2; penanda dapat digeser dan dipindah dengan tombol panah (1 px, Shift = 10 px). Koordinat dipetakan dari ukuran tampilan ke dimensi citra asli.
  3. Input "Panjang fisik segmen (cm)", tampil Δpx, skala (cm/px), dan estimasi luas cm².
  4. Tombol **Terapkan Kalibrasi** (memanggil `PUT`), **Ulangi Titik**, **Hapus Kalibrasi**.
  5. Peringatan tetap G6 di bawah panel.
- Dialog "Konfirmasi dan Simpan" menyebut mode pengukuran (terkalibrasi atau relatif) dan pernyataan pemeriksaan masker tetap wajib.

**Final**
- Lencana mode ukur: **"Terkalibrasi · cm²"** atau **"Basis Relatif · %"**.
- Kartu luas: nilai utama sesuai mode (cm² bila terkalibrasi, dengan "setara x% dari citra" di bawahnya). Catatan batas "bukan ukuran dalam cm²" hanya tampil pada mode relatif.
- Kartu PAC: label basis, ΔA dalam satuan yang sesuai, peringatan G5 (komponen amber di kartu PAC), dan catatan `MIXED_BASIS`.
- Rincian perhitungan (disclosure tertutup): PAC relatif sebagai pembanding bila `pac_cm2` ada.
- Grafik tren PAC: sumbu Y **dinamis** (mockup lama menetapkan 0–30% sehingga PAC negatif atau > 30% keluar grafik). Titik berbasis berbeda memakai penanda berbeda dan tooltip menyebut basis.
- Narasi mengikuti Bagian 7.

## 7. Narasi LLM: Satuan dan Validator

- System prompt (Tabel 3.4) tidak berubah. User prompt: A₀, Aₜ, ΔA, PAC, status tren, ditambah `satuan` (`"%"` atau `"cm²"`; D3). ΔA berupa "poin persentase" pada mode relatif dan "cm²" pada mode terkalibrasi.
- Templat fallback (Tabel 3.5) memakai variabel `{satuan}` dan `{satuan_delta}`. Pola kalimat selain itu tidak diubah.
- Validator angka: semua angka pada narasi harus ada dalam himpunan angka masukan (format koma desimal, nilai mutlak untuk PAC negatif). Angka asing menyebabkan narasi dibuang dan fallback dipakai.
- Tambahkan tes validator untuk narasi bersatuan cm².
- Narasi tidak boleh menyebut kata "membaik", "sembuh", atau diagnosis (aturan PRD v2 tidak berubah).

## 8. Penyesuaian Fase 4, 5, dan PRD v2 Bagian 10

**Fase 4 (H5)**: kolom luas menampilkan nilai utama dengan satuannya; tiap baris punya tag basis (`cm²` atau `%`); grafik memakai sumbu dinamis dan penanda per basis seperti H4. Baris dengan peringatan menampilkan ikon peringatan beserta tooltip.

**Fase 5**: skrip seeding LUTSeg membuat kunjungan **tanpa** kalibrasi. Uji SK-2d (Patient_17) dijalankan lewat skrip terpisah yang memanggil `PUT /visits/{id}/calibration` dengan titik yang dicatat manual dalam berkas JSON. Skrip menyimpan `pac_rel`, `pac_cm2`, dan skala dua kunjungan untuk analisis.

**PRD v2 Bagian 10.4**: opsi A (kolom jarak kamera) tidak dipakai karena digantikan kalibrasi; opsi B (simpan status centang) boleh dikerjakan; opsi C tidak disarankan; opsi D tetap pengembangan lanjutan.

## 9. Daftar Update Mockup

### 9.1 `h3_unggah_foto.html`

| # | Perubahan |
| :--- | :--- |
| H3-1 | Ganti blok `.ref` dengan panel acuan bertab (Baseline bawaan, Kunjungan Terakhir). Satu tab bila kunjungan terakhir adalah baseline. Data demo: baseline 01 Okt 2026, terakhir 17 Okt 2026 |
| H3-2 | Bungkus `<img id="img">` dalam `.stack{position:relative}`. Tambahkan `<img class="ghost">` dengan `position:absolute; inset:0; object-fit:contain; pointer-events:none; opacity:var(--ghost)` dan `aria-hidden="true"` |
| H3-3 | Baris kontrol di bawah pratinjau: saklar overlay + slider 0–80 (bawaan 40) dengan `<output>`. Sembunyikan pada mode kunjungan 1. Reset saat `clearPhoto()` |
| H3-4 | Teks bantu overlay dan teks kotak centang baru (Bagian 4) |
| H3-5 | Panduan: tambah butir ke-5 (penggaris) dan ganti catatan bawah (Bagian 4 butir 4). `.guide li` sudah berbasis grid sehingga butir baru tidak memerlukan CSS tambahan |
| H3-6 | `handleFile`: cek `['image/jpeg','image/png'].includes(f.type)`; ubah pesan error; set `tgl.min` |
| H3-7 | Label tombol sampel menjadi "Gunakan Foto Sampel (Mode demo)" |
| H3-8 | Opsional: demo state "Ada draf belum disimpan" (PRD v2 10.2 butir 3) dengan tombol Lanjutkan draf / Buang draf |

### 9.2 `h4_hasil_kunjungan.html`

| # | Perubahan |
| :--- | :--- |
| H4-1 | State `draft`: sembunyikan `tabsCard`, tampilkan placeholder narasi. Kartu PAC berlabel "Pratinjau PAC (belum disimpan)". Mockup lama menampilkan narasi LLM pada draf, padahal narasi baru dibuat saat konfirmasi |
| H4-2 | Tambah panel Kalibrasi Penggaris pada state draf (spesifikasi Bagian 6). Gambar foto asli pada `<canvas>`, simpan dua titik dalam koordinat asli (`natural = displayed × W/clientWidth`). Fungsi hitung: `s = L/Δpx`, `areaCm2 = (nLuka/65536) × W × H × s²` |
| H4-3 | Lencana mode ukur pada kartu luas; nilai utama cm² dan sub-teks "setara x% dari citra". Catatan `.m-limit` dibuat kondisional |
| H4-4 | Kartu PAC: label basis, komponen peringatan G5 (`.fluct` amber dapat dipakai ulang), catatan `MIXED_BASIS` |
| H4-5 | Disclosure "Rincian perhitungan" berisi PAC relatif pembanding (tampil bila terkalibrasi) |
| H4-6 | Grafik: ganti `VB.ymax=30` dan `py()` dengan rentang dinamis (termasuk nilai negatif); tick otomatis; penanda berbeda per basis |
| H4-7 | Tab narasi: varian teks statis untuk mode relatif dan terkalibrasi (satuan sesuai) |
| H4-8 | Dialog konfirmasi menyebut mode ukur |
| H4-9 | Tombol "Foto Ulang" tetap; tambah teks bantu bahwa kalibrasi akan terhapus bersama draf |

**State demo H4 (panel `.seg`)**

| State | Data | Yang didemokan |
| :--- | :--- | :--- |
| Baseline | A₀ = 10,26% | Tanpa PAC |
| Draf (relatif) | Aₜ = 8,10%, PAC pratinjau +21,1% | Panel kalibrasi tertutup |
| Draf (kalibrasi) | Foto bergaris penggaris, Δpx = 80, L = 2 cm | Pratinjau PAC berubah setelah Terapkan |
| Final (relatif) | Aₜ = 8,10%, PAC +21,1% | Tanpa peringatan |
| Final (peringatan) | Aₜ = 9,54%, PAC +7,0% | `DISTANCE_SENSITIVE` |
| Final (kalibrasi) | A₀ = 12,40 cm² (10,26%), Aₜ = 12,40 cm² (6,57%) | PAC cm² = 0,0% Stabil; PAC relatif pembanding +36,0% |

Catatan untuk state terakhir: pada mode relatif, perubahan 10,26% ke 6,57% menghasilkan PAC +36,0% dan memicu `DISTANCE_LARGE` (D1). Tambahkan satu state demo "Final (relatif, PAC besar)" dengan data yang sama tetapi tanpa kalibrasi, agar peringatan kuat terlihat berdampingan dengan versi terkalibrasinya.

## 10. Dampak ke Proposal (untuk Anda, bukan untuk Argon)

- Tambah subbab 3.7.5 "Kalibrasi Penggaris Dua Titik (Opsional)": rumus G2, aturan G3, dan batasan G6.
- D1: di Subbab 3.7.3 hapus batas atas 10% pada kalimat peringatan. Tulis bahwa peringatan berlaku untuk |PAC| ≥ 5,0% pada mode tanpa kalibrasi, dengan teks lebih kuat di atas 10%. Tambahkan alasannya (pergeseran 20→25 cm setara PAC semu 36%).
- D2: tambahkan catatan kaki Tabel 3.3: pada mode terkalibrasi status tren ditentukan PAC cm² saja.
- D3: sebut string satuan pada Subbab 3.8.2 dan sesuaikan kasus K10 (payload berisi lima angka dan satu string satuan, tetap tanpa citra, nama, atau nomor RM).
- Gambar 3.1 sampai 3.3 dan mockup 3.9–3.10 diperbarui mengikuti dokumen ini.
