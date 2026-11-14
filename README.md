# WoundAI — Sistem Pemantauan Longitudinal Ulkus Kusta

Aplikasi web prototipe untuk membantu dokumentasi, segmentasi, dan pemantauan longitudinal ulkus kusta secara objektif menggunakan citra klinis, perhitungan **Percentage Area Change (PAC)**, kalibrasi dua titik opsional (`cm²`), serta ringkasan narasi dual-audiens berbasis Google Gemini API dengan fallback templat deterministik.

---

## Ringkasan Arsitektur & Fitur Utama

1. **Segmentasi Luka Otomatis (PyTorch U-Net ResNet-34)**:
   - Citra masukan diubah ukurannya menjadi `256×256` piksel, dinormalisasi (bawaan `zero_one`, atau `imagenet` sesuai konfigurasi), lalu diproses untuk menghasilkan masker biner luka (`threshold = 0,5`, $N_{\text{total}} = 65.536$).
   - Luas relatif awal dihitung sebagai $A_t = (N_{\text{luka}} / 65.536) \times 100\%$.
2. **Kalibrasi Dua Titik Opsional & Mode Ganda (`%` vs `cm²`)**:
   - Pada kunjungan berstatus `draft`, klinisi dapat mengkalibrasi skala piksel dengan menandai dua titik acuan (misalnya mistar/penggaris pada bidang luka) serta memasukkan panjang nyata dalam sentimeter (`0 < length_cm ≤ 50`).
   - Jika seluruh kunjungan yang dibandingkan terkalibrasi, evaluasi longitudinal menggunakan satuan absolut **$\text{cm}^2$** dan menampilkan peringatan perubahan jarak pemotretan bila terdeteksi selisih skala atau perubahan ekstrem. Jika salah satu belum terkalibrasi, sistem menggunakan basis relatif `%` secara otomatis disertai penanda `MIXED_BASIS`.
3. **Pelacakan Longitudinal & Klasifikasi Tren**:
   - Kunjungan terkonfirmasi pertama ($t = 1$) menjadi baseline $A_0$ (tanpa perhitungan PAC dan tanpa panggilan LLM).
   - Kunjungan lanjutan ($t \ge 2$) menghitung $\text{PAC} = ((A_0 - A_t) / A_0) \times 100\%$, $\Delta A = A_t - A_0$, serta klasifikasi status tren (**Menurun / Mengecil**, **Stabil**, atau **Meningkat / Membesar**).
4. **Alur Draf → Final & Penghapusan LIFO**:
   - Hasil unggahan baru berstatus `draft` dan dapat dibuang (*Foto Ulang*) atau dikonfirmasi menjadi `final`.
   - Penghapusan kunjungan hanya diizinkan pada kunjungan terakhir pasien (**Last-In, First-Out / LIFO**) demi menjaga integritas deret longitudinal.
5. **Narasi Dual-Audiens dengan *Factual Grounding* & Fallback Deterministik**:
   - Hanya parameter numerik terhitung ($A_0, A_t, \Delta A, \text{PAC}$, status tren, dan `satuan` saat mode `cm²`) yang dikirim ke model Gemini — tanpa PII pasien dan tanpa foto luka mentah.
   - Keluaran LLM wajib lolos validator ketat (bebas kata terlarang, memuat disclaimer estimasi foto, bebas angka asing, konsisten arah tren, dan memakai koma desimal). Jika Gemini timeout (`>10s`), gagal, atau ditolak validator, sistem segera memakai templat fallback deterministik (`narrative_source = "template_fallback"`) tanpa menggagalkan penyimpanan kunjungan.

---

## Prasyarat

- **Docker** & **Docker Compose** (v2+)
- **Node.js 22+** & **npm** (opsional, untuk menjalankan pemeriksaan dan unit test frontend secara lokal di `frontend/`)

---

## Konfigurasi Lingkungan (`.env`)

Salin berkas contoh konfigurasi terlebih dahulu:

```bash
cp .env.example .env
```

Lalu sesuaikan seperlunya di `.env` (berkas `.env` diabaikan oleh Git agar kunci rahasia tidak ikut terkomit):

| Variabel | Bawaan | Keterangan |
| --- | --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | `woundai` / `changeme_local_only` / `woundai_db` / `5435` | Kredensial & port PostgreSQL lokal |
| `DATABASE_URL` / `TEST_DATABASE_URL` | Port `5435` ke `woundai_db` / `woundai_test` | Dipakai untuk eksekusi di luar container |
| `MODEL_CHECKPOINT_PATH` | `ml/checkpoints/best_resnet34_unet_01norm.pth` (lokal) / `/app/checkpoints/best_resnet34_unet_01norm.pth` (Docker) | Lokasi berkas bobot `.pth` U-Net ResNet-34 |
| `MODEL_NORMALIZATION` | `zero_one` | Mode normalisasi masukan (`zero_one` atau `imagenet`) |
| `MODEL_INPUT_SIZE` | `256` | Resolusi masukan citra (piksel persegi, rentang `64–1024`) |
| `MODEL_BINARY_THRESHOLD` | `0.5` | Ambang probabilitas sigmoid masker biner (`0 < t < 1`) |
| `GEMINI_API_KEY` | *(kosong)* | Kunci Google Gemini API; bila kosong sistem selalu memakai `template_fallback` |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Nama model Gemini yang dipanggil |
| `GEMINI_TEMPERATURE` | `0.3` | Temperatur generasi |
| `GEMINI_MAX_OUTPUT_TOKENS` | `800` | Batas maksimum token keluaran |
| `GEMINI_TIMEOUT_SECONDS` | `10.0` | Batas waktu HTTP sebelum beralih ke fallback |
| `SEED_DEMO_ON_STARTUP` | `false` | Jika `true`, container backend mengisi data demo dasar saat startup |

> **Catatan keamanan:** Jangan pernah menuliskan nilai asli `GEMINI_API_KEY` di `.env.example`, kode sumber, atau log.

---

## Menjalankan Sistem dari Kondisi Bersih

Untuk memastikan database, volume unggahan, dan container dibangun ulang dari nol:

```bash
docker compose down -v
docker compose up --build -d
```

Proses startup container `woundai-backend` menjalankan `alembic upgrade head` secara otomatis sebelum menyalakan server Uvicorn FastAPI, sehingga seluruh tabel PostgreSQL terbentuk tanpa perintah migrasi manual.

Verifikasi status container dan endpoint kesehatan:

```bash
docker compose ps
curl http://localhost:8000/api/v1/health
```

Antarmuka web dapat diakses pada **`http://localhost:5173`** dan dokumentasi API backend pada **`http://localhost:8000/docs`**.

---

## Mengelola Data Demo (`seed_h3_demo`)

Untuk mengisi pasien & kunjungan demo (termasuk sampel kalibrasi `RM-0010`, `RM-0016`, `RM-0024` beserta citra uji):

```bash
docker exec woundai-backend python -m app.services.seed_h3_demo
```

Untuk membersihkan kembali seluruh data & citra demo dari database maupun penyimpanan lokal:

```bash
docker exec woundai-backend python -m app.services.seed_h3_demo --clear
```

---

## Mengganti Checkpoint Model Segmentasi

Aplikasi membaca seluruh parameter inferensi dari konfigurasi sehingga model dapat ditukar setelah training baru tanpa mengubah kode:

1. Letakkan berkas bobot baru (format `.pth` PyTorch untuk arsitektur `ResNet34UNet`) ke direktori **`ml/checkpoints/`**, misalnya `ml/checkpoints/resnet34_unet_final_imagenet.pth`.
   - Di dalam Docker Compose, direktori `./ml/checkpoints` di-mount ke `/app/checkpoints:ro` di container backend.
2. Perbarui variabel lingkungan di `.env`:
   ```env
   MODEL_CHECKPOINT_PATH=/app/checkpoints/resnet34_unet_final_imagenet.pth
   MODEL_NORMALIZATION=imagenet   # pilih "zero_one" (x/255) atau "imagenet" ((x/255 - mean)/std)
   MODEL_INPUT_SIZE=256           # opsional, bawaan 256
   MODEL_BINARY_THRESHOLD=0.5     # opsional, bawaan 0.5
   ```
   *(Jika menjalankan backend langsung di host tanpa Docker, gunakan path relatif host seperti `ml/checkpoints/resnet34_unet_final_imagenet.pth`.)*
3. Recreate container backend agar konfigurasi dan bobot baru dimuat ulang:
   ```bash
   docker compose up -d backend
   ```
4. Verifikasi identitas model aktif melalui `GET /api/v1/health`:
   ```json
   "model": {
     "checkpoint_name": "resnet34_unet_final_imagenet.pth",
     "checkpoint_sha256_short": "...",
     "loaded": true,
     "normalization": "imagenet",
     "input_size": 256,
     "binary_threshold": 0.5
   }
   ```
   - Jika path checkpoint tidak ditemukan saat startup/inferensi, sistem memunculkan galat jelas (`FileNotFoundError`) dan melaporkan `"loaded": false`.
   - Nilai konfigurasi yang tidak valid (misalnya `MODEL_NORMALIZATION` di luar `zero_one`/`imagenet`, ukuran di luar rentang, atau ambang di luar `(0, 1)`) langsung ditolak saat validasi startup.

---

## Menjalankan Pengujian

### Backend (`pytest` di dalam container)

```bash
# Seluruh tes otomatis (database uji terisolasi woundai_test)
docker exec woundai-backend pytest -v

# Termasuk pengujian API Gemini asli (membutuhkan GEMINI_API_KEY valid pada environment backend)
docker exec -e RUN_REAL_GEMINI=1 woundai-backend pytest -v -s
```

### Frontend (di direktori `frontend/`)

```bash
cd frontend
npm run typecheck
npm run build
npm run test:unit
```

---

## Batasan Prototipe Klinis

- **Bukan alat diagnosis mandiri**: Keluaran luas luka, klasifikasi tren PAC, maupun narasi otomatis hanyalah estimasi berbasis citra 2D dan **tidak menggantikan pemeriksaan klinis langsung** oleh dokter atau perawat terlatih.
- **Ketergantungan sudut & jarak pemotretan**: Pada mode relatif (`%`), perbedaan jarak kamera atau pembingkaian foto memengaruhi persentase piksel luka terhadap total bingkai.
- **Akurasi kalibrasi dua titik**: Mode terkalibrasi (`cm²`) berasumsi objek acuan berada **di bidang datar yang sama** dengan permukaan luka, tegak lurus terhadap sumbu optik kamera, dan kedua titik ditandai secara presisi.
- **Kualitas citra & pencahayaan**: Foto dengan blur gerak berat, pencahayaan sangat minim, atau luka yang tertutup perban/bayangan kuat dapat menurunkan keandalan segmentasi otomatis.
