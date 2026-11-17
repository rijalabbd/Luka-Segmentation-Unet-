# Panduan Akses WoundAI dari Ponsel (Jaringan Lokal / LAN)

Panduan ini menjelaskan cara membuka aplikasi WoundAI di ponsel melalui Wi-Fi lokal atau hotspot laptop tanpa membuka layanan ke internet publik.

## 1. Catatan Keamanan & Tahap Pengembangan

- **Privasi Data:** Konfigurasi bawaan (`docker-compose.yml`) mengikat seluruh port ke `127.0.0.1` (hanya bisa diakses dari laptop itu sendiri). Gunakan berkas override `docker-compose.lan.yml` **hanya saat sesi uji atau pemakaian di jaringan lokal terpercaya**, lalu matikan kembali setelah selesai.
- **Tahap 1 vs Tahap 2:** Pada Tahap 1 ini aplikasi berjalan lewat **HTTP biasa (`http://...`)** dengan tombol **Ambil Foto** yang memanggil kamera bawaan ponsel (`<input capture="environment">`). Fitur kamera langsung di halaman web (`getUserMedia` dengan bayangan foto awal) membutuhkan **HTTPS** dan akan dikerjakan pada **Tahap 2**.

## 2. Cek Alamat IP Laptop di Windows

1. Buka PowerShell atau Command Prompt di laptop.
2. Jalankan perintah:
   ```powershell
   ipconfig
   ```
3. Cari bagian adaptor Wi-Fi aktif (**Wireless LAN adapter Wi-Fi**) atau hotspot, lalu catat nilai **IPv4 Address** (contoh: `192.168.1.25` atau `192.168.137.1`).

## 3. Izinkan Port di Windows Firewall (Sekali Saja)

Agar ponsel dapat menjangkau port aplikasi (`5173`) melalui jaringan lokal Windows (**profil Private**), tambahkan aturan inbound di PowerShell (Run as Administrator):

```powershell
New-NetFirewallRule -DisplayName "WoundAI LAN Frontend 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow -Profile Private
```

*(Opsional)* Jika Anda juga ingin menguji endpoint backend secara langsung pada port `8000`:

```powershell
New-NetFirewallRule -DisplayName "WoundAI LAN Backend 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
```

> Pastikan profil jaringan Wi-Fi / hotspot di Windows disetel sebagai **Private network**, bukan Public. Untuk menghapus aturan setelah pengujian:
> `Remove-NetFirewallRule -DisplayName "WoundAI LAN Frontend 5173","WoundAI LAN Backend 8000"`

## 4. Menyalakan & Mematikan Mode LAN

**(Opsional)** Jika backend diakses langsung tanpa proxy atau jika `CORS_ORIGINS` perlu mencantumkan IP laptop Anda, tambahkan IP tersebut ke `.env` sebelum menyalakan container (frontend secara bawaan berkomunikasi lewat path relatif `/api/v1` melalui proxy Vite sehingga tetap bekerja dari port `5173`):

```env
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://192.168.1.25:5173"]
```

Nyalakan aplikasi dalam mode LAN:

```powershell
docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d
```

Kembalikan ke mode aman (`127.0.0.1` saja) setelah selesai:

```powershell
docker compose up -d
```

## 5. Alamat yang Dibuka di Ponsel

Hubungkan ponsel ke jaringan Wi-Fi yang **sama** dengan laptop, lalu buka Chrome (Android) atau Safari (iOS) dan ketik:

```text
http://<IP-laptop>:5173
```

Contoh: `http://192.168.1.25:5173`

## 6. Jika Wi-Fi Kampus / Klinik Mengisolasi Perangkat

Banyak Wi-Fi kampus atau publik mengaktifkan fitur *AP/Client Isolation* sehingga ponsel tidak bisa terhubung ke IP laptop meskipun berada di Wi-Fi yang sama. Solusinya:

- Nyalakan **Mobile Hotspot** bawaan Windows 11/10 di laptop, lalu sambungkan ponsel ke hotspot laptop tersebut (IP laptop biasanya menjadi `192.168.137.1`, sehingga alamat di ponsel adalah `http://192.168.137.1:5173`), **atau**
- Gunakan router Wi-Fi lokal kecil (off-grid tanpa perlu internet), disarankan dengan **IP statis/tetap** untuk laptop saat demo agar `LAN_HOST` tidak berubah.

## 7. Mode HTTPS LAN (Tahap 2 — Kamera Langsung dengan Bayangan)

Kamera langsung (`getUserMedia`) di browser ponsel hanya diizinkan pada konteks aman (`https://`). Tahap 2 menyediakan reverse proxy **Caddy** (`docker-compose.https.yml` + `Caddyfile`) pada port **443** (atau `8443` jika port `443` bentrok).

### Menyalakan mode HTTPS

1. Setel `LAN_HOST` di `.env` (atau di PowerShell) sesuai IP laptop dari `ipconfig`:
   ```env
   LAN_HOST=192.168.11.119
   ```
2. Izinkan port `443` di Windows Firewall (profil Private):
   ```powershell
   New-NetFirewallRule -DisplayName "WoundAI LAN HTTPS 443" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow -Profile Private
   ```
3. Jalankan stack HTTPS:
   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.lan.yml -f docker-compose.https.yml up -d
   ```
   *(Jika port 443 dipakai aplikasi lain, jalankan dengan `HTTPS_PORT=8443` di `.env` lalu buka `https://<IP-laptop>:8443`.)*
4. Buka di ponsel:
   ```text
   https://<IP-laptop>
   ```
   Contoh: `https://192.168.11.119`

### Melewati peringatan sertifikat di ponsel

Karena Caddy memakai `tls internal` (sertifikat lokal mandiri), browser ponsel akan menampilkan peringatan keamanan pada kunjungan pertama:

- **Chrome (Android):** Tekan **Lanjutan (Advanced) → Lanjutkan ke `<IP-laptop>` (tidak aman)**.
- **Safari (iOS):** Tekan **Tampilkan Detail (Show Details) → Kunjungi situs web ini (visit this website)** lalu konfirmasi.

### Memasang sertifikat akar Caddy (opsional, agar peringatan hilang)

1. Salin sertifikat akar internal Caddy dari container ke laptop:
   ```powershell
   docker cp woundai-caddy:/data/caddy/pki/authorities/local/root.crt .\caddy-root.crt
   ```
2. Kirim berkas `caddy-root.crt` ke ponsel:
   - **Android:** Buka **Setelan → Keamanan / Enkripsi & kredensial → Pasang sertifikat → Sertifikat CA**, pilih `caddy-root.crt`.
   - **iOS:** Buka berkas `caddy-root.crt` untuk mengunduh profil, lalu **Settings → General → VPN & Device Management** (pasang profil), kemudian aktifkan kepercayaan penuh di **Settings → General → About → Certificate Trust Settings**.

### Memperbarui `LAN_HOST` saat IP laptop berganti

Jika IP laptop berubah saat berpindah jaringan:
1. Cek IP baru dengan `ipconfig`.
2. Ubah `LAN_HOST=<IP-baru>` di `.env`.
3. Jalankan ulang container agar Caddy menerbitkan sertifikat dan Vite memperbarui `allowedHosts`:
   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.lan.yml -f docker-compose.https.yml up -d --force-recreate frontend caddy
   ```

## 8. Tabel Galat Umum

| Gejala / Galat | Penyebab | Solusi |
| --- | --- | --- |
| Peringatan sertifikat (`NET::ERR_CERT_AUTHORITY_INVALID`) | Browser belum mengenali CA internal Caddy (`tls internal`). | Lewati peringatan lewat menu *Lanjutan / Advanced*, atau pasang `root.crt` Caddy di ponsel. |
| Izin kamera ditolak (`NotAllowedError`) | Pengguna menolak izin kamera atau situs dibuka lewat `http://` biasa. | Pastikan membuka alamat `https://`, lalu izinkan kamera di pengaturan situs browser. Jika tetap ditolak, tekan **Pakai kamera bawaan**. |
| `Blocked request. This host is not allowed.` (`allowedHosts` salah) | `LAN_HOST` yang dikirim ke container `frontend` tidak cocok dengan host/IP di URL browser. | Samakan `LAN_HOST` di `.env` dengan IP laptop yang diakses, lalu recreate container `frontend`. |
| Port 443 bentrok (`bind: address already in use`) | Aplikasi lain di Windows memakai port `443`. | Setel `HTTPS_PORT=8443` di `.env` (dan buka firewall TCP `8443`), lalu akses `https://<IP-laptop>:8443`. |
| IP laptop berganti setelah reconnect Wi-Fi | DHCP router memberi IP baru pada laptop. | Cek IP baru (`ipconfig`), perbarui `LAN_HOST` di `.env`, lalu recreate `frontend` dan `caddy`; atau gunakan Mobile Hotspot / router IP statis saat demo. |

---

## Uji manual di ponsel (dikerjakan pemilik proyek)

1. Nyalakan mode LAN, buka alamat dari Chrome Android. Beranda tampil dan indikator "Server terhubung" hijau.
2. Pilih pasien, buka H3. "Ambil Foto" membuka kamera belakang. Foto yang diambil muncul di pratinjau.
3. "Dari galeri" membuka pemilih foto. Foto terpilih muncul di pratinjau.
4. Analisis foto portrait asli dari ponsel. Overlay di halaman hasil sejajar dengan foto.
5. Ulangi di iOS Safari bila ada perangkatnya.
6. Catat ukuran berkas dan waktu analisis.
