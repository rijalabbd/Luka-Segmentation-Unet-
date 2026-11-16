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
- Gunakan router Wi-Fi lokal kecil (off-grid tanpa perlu internet).

---

## Uji manual di ponsel (dikerjakan pemilik proyek)

1. Nyalakan mode LAN, buka alamat dari Chrome Android. Beranda tampil dan indikator "Server terhubung" hijau.
2. Pilih pasien, buka H3. "Ambil Foto" membuka kamera belakang. Foto yang diambil muncul di pratinjau.
3. "Dari galeri" membuka pemilih foto. Foto terpilih muncul di pratinjau.
4. Analisis foto portrait asli dari ponsel. Overlay di halaman hasil sejajar dengan foto.
5. Ulangi di iOS Safari bila ada perangkatnya.
6. Catat ukuran berkas dan waktu analisis.
