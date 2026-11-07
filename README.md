# Neotest Kiosk 3.4.0

Versi pengembangan dari `neotest.txt` (sebelumnya bernama CakBro). Aplikasi menggunakan Qt WebEngine di dalam jendela fullscreen; tidak mengendalikan browser pribadi.

## Perilaku

- Isi halaman ditampilkan apa adanya. Tidak ada kode bridge judul, hitung mundur, peringatan 5 menit/1 menit/30 detik, overlay waktu habis, injeksi JavaScript, atau klik otomatis dari aplikasi. Jika situs web sendiri menampilkan peringatan atau melakukan tindakan, ubah kode situs tersebut secara terpisah.
- Tombol **Home** memuat URL home yang berlaku, tanpa menambahkan parameter dan tanpa menghapus cookie atau profil. Perubahan formulir yang belum tersimpan bisa hilang. Tombol keluar telah dihapus. Untuk menutup aplikasi secara normal, tekan **Ctrl+Shift+Alt+Q** bersamaan; pada macOS gunakan tombol Control fisik, bukan Command. Jika masih ada pemeriksaan jaringan saat startup, tunggu selesai lalu tekan lagi.
- Profil dan cache WebEngine Neotest terpisah dari browser pribadi. Aplikasi tidak menutup aplikasi lain dan tidak menghapus data browser lain.
- **Shortcut dalam aplikasi:** filter mencoba memblokir F1/F3/F5/F6/F10/F11/F12, Print Screen, tombol menu/Meta, Ctrl atau Command dengan B/C/D/E/F/G/H/J/K/L/N/O/P/Q/R/S/T/U/V/W/X, Tab/PageUp/PageDown/Esc (kecuali Ctrl+Shift+Alt+Q untuk keluar), Ctrl/Command+Shift+I/J/C/K/M/N/T/P/S/Esc, serta Alt+Tab/Esc/F4/panah kiri/kanan/Space/Home. Menu konteks dan permintaan jendela/tab baru juga ditolak. Tombol refresh, cari, copy-paste, dan fungsi lain mungkin tidak bekerja. Ini bisa mengganggu situs dan login popup; lakukan uji terlebih dahulu.
- **Windows:** hook keyboard global best-effort mencoba memblokir **tombol Windows kiri dan kanan** baik ditekan sendiri maupun dalam kombinasi, serta shortcut di atas. Beberapa tombol khusus keyboard browser (Back/Forward/Refresh/Stop/Search/Favorites/Home) dan peluncur aplikasi/mail juga diblokir. Hook berpengaruh pada aplikasi lain selama Neotest aktif. Jika gagal saat pemasangan, ada peringatan dan aplikasi tetap berjalan dengan filter Qt; Windows juga dapat menghapus hook secara diam-diam. Ini bukan jaminan keamanan.
- **Linux dan macOS:** penyaringan hanya pada event keyboard yang diterima aplikasi; shortcut yang ditangani sistem (termasuk berpindah aplikasi, screenshot, dan shortcut compositor seperti Wayland) bisa lolos. Windows juga tidak dapat menjamin pemblokiran Ctrl+Alt+Del, Win+L, semua cara screenshot/rekam layar, atau software/perangkat eksternal. Aplikasi tidak mencegah foto layar menggunakan perangkat lain.
- **Keamanan penting:** kombinasi keluar tidak memakai PIN dan dapat digunakan siapa saja yang mengetahuinya. Pada Windows, hook keyboard mencoba menerima shortcut tersebut secara global; jika hook gagal, shortcut hanya berfungsi saat event keyboard sampai ke jendela aplikasi. Pada Linux/macOS, fokuskan jendela Neotest sebelum menekan shortcut; OS atau compositor mungkin mengambil kombinasi tersebut. Penutupan dari window manager biasa ditolak, tetapi admin/OS masih dapat memaksa penghentian, mematikan perangkat, atau melakukan tindakan darurat. Aplikasi tetap bisa berhenti dan memulai ulang sendiri untuk memasang update. Ini bukan penguncian perangkat yang aman untuk ujian. Gunakan konfigurasi kiosk/assigned access dan kebijakan sistem masing-masing OS, serta pengawasan dan uji perangkat nyata, jika dibutuhkan.
- Ini WebEngine berbasis Chromium, bukan Edge/Chrome/Firefox yang sudah terpasang. Situs atau alur login tertentu, khususnya popup/jendela baru yang sekarang diblokir, mungkin perlu penyesuaian dan harus diuji di lingkungan sebenarnya.

## Satu kali: unggah ke GitHub

1. Buat atau gunakan repository **publik** `pakkar1/cakbro-updates` (nama repository sengaja tetap sama agar updater versi lama dapat menemukannya), atau ubah `GITHUB_REPO` di `neotest.py` menjadi `pemilik/nama-repo` Anda **sebelum build pertama**. Mengganti repository memutus pemeriksaan update pada binary lama yang masih menunjuk ke repository sebelumnya; perangkat tersebut perlu dimigrasikan secara terpisah. Sesuaikan `GITHUB_BRANCH` jika cabang default bukan `main`. URL bawaan `DEFAULT_URL` juga dapat diubah.
2. Unggah **isi** folder proyek ini ke root repository, termasuk `.github/workflows/build.yml` dan `config.json` (file tersembunyi `.github` wajib ikut). Aktifkan GitHub Actions dan pastikan Actions diizinkan membuat release. Biner lama 3.0 tidak otomatis berubah menjadi versi ini: instal/salin binary baru setidaknya sekali.
3. `config.json` berisi `home_url` HTTPS. Ubah dan commit ke cabang yang ditentukan untuk memperbarui URL, tanpa build ulang atau instal ulang. Perubahan dipakai saat aplikasi berikutnya dijalankan, lalu tombol Home memakai URL itu. Jika offline, URL terakhir yang berhasil diunduh dipakai; jika belum ada cache, URL bawaan dipakai. Perubahan tidak memindahkan halaman secara otomatis saat pengguna sedang menggunakannya.
4. Untuk build percobaan, buka **Actions → Build dan rilis Neotest → Run workflow**. Hasilnya tersedia sebagai Actions artifacts, tanpa release otomatis. Unduh dan uji di tiap platform target.
5. Untuk rilis, ubah `APP_VERSION` di `neotest.py` menjadi versi baru `major.minor.patch`, commit dan push; buat dan push tag yang sama, misalnya `v3.4.0` untuk `APP_VERSION = "3.4.0"`:

   ```bash
   git add .
   git commit -m "Neotest 3.4.0"
   git push origin main
   git tag v3.4.0
   git push origin v3.4.0
   ```

   Workflow mem-build empat aset utama bernama `Neotest-*` (Windows x64, Linux x64, macOS Apple Silicon dan Intel), menghasilkan `SHA256SUMS.txt`, lalu membuat GitHub Release setelah semua build sukses. Untuk kompatibilitas auto-update versi CakBro 3.1/3.2, rilis juga menyertakan salinan aset bernama `CakBro-*`; keduanya berisi aplikasi Neotest yang sama. Pengguna baru sebaiknya mengunduh aset `Neotest-*`. Perubahan otomatis hanya bekerja jika perangkat lama masih memeriksa repository yang sama dan dapat mengganti binary. Setelah update, nama file executable lama tidak diubah otomatis walaupun aplikasi yang berjalan bernama Neotest. Jika tag sudah ada, gunakan versi/tag baru. Lihat log Actions bila build gagal. Fitur Actions/runners tergantung pengaturan dan kuota akun GitHub.
6. Unduh aset dari **Releases** untuk tiap komputer, simpan di folder yang dapat ditulis oleh pengguna. Di Linux/macOS mungkin perlu `chmod +x nama-file`. Aplikasi dan Qt WebEngine dapat berukuran besar. macOS unsigned/unnotarized dan Windows tanpa code signing dapat memunculkan peringatan OS; kebijakan organisasi bisa memblokirnya. Proses signing/notarization belum disertakan.

## Pembaruan otomatis aplikasi

Saat **mulai**, build binary memeriksa latest stable release GitHub. Jika versinya lebih baru dan terdapat aset platform serta SHA-256 yang cocok, unduhan diverifikasi dan helper memasang binary dengan `os.replace`, lalu memulai ulang aplikasi. Tidak perlu menjalankan installer ulang. Pemeriksaan/unduhan dilakukan sebelum halaman ditampilkan, sehingga dapat memakan waktu sesuai jaringan dan ukuran aset. Tidak ada update binary otomatis di tengah sesi; tutup dan jalankan ulang untuk memeriksa lagi. Jika unduhan, verifikasi, jaringan, atau izin gagal, aplikasi melanjutkan dengan versi lama. Jika penggantian gagal, versi lama dijalankan ulang dengan pemeriksaan update dilewati pada startup tersebut. Binary harus berada di folder yang dapat ditulis, dan perangkat harus memiliki akses HTTPS ke GitHub dan host aset release. Repository privat belum didukung.

SHA-256 mendeteksi kerusakan/ketidakcocokan tetapi **bukan tanda tangan digital**: pihak yang dapat mengubah release beserta checksum dapat mengganti aplikasi. Lindungi akun/repository (2FA, perlindungan tag/branch dan izin rilis). Backup binary sebelumnya dan uji rilis sebelum produksi. Auto-update tidak didukung pada mode skrip Python, tetapi konfigurasi URL tetap diperiksa.

## Menjalankan dari source untuk pengembangan

Python 3.11 disarankan. Harus ada lingkungan desktop grafis; Linux mungkin memerlukan library Qt/Chromium seperti paket yang dipasang workflow. Jalankan:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python neotest.py
python -m unittest discover -s tests -v
```

Konfigurasi, cache situs, dan log `neotest.log` disimpan di direktori data pengguna: `%LOCALAPPDATA%/Neotest` di Windows, `~/.local/share/Neotest` di Linux (atau `$XDG_DATA_HOME/Neotest`), `~/Library/Application Support/Neotest` di macOS. Bila folder Neotest belum ada tetapi folder lama CakBro ada, folder lama tetap dipakai agar konfigurasi dan profil sebelumnya tidak dihapus. Jika keduanya ada, Neotest diprioritaskan; tidak ada penggabungan otomatis. Backup data dan uji sesi login saat migrasi. Log dapat berisi detail kesalahan jaringan; perlakukan sebagai data lokal.

## Catatan verifikasi

Paket ini disiapkan secara lokal; repository belum diunggah dan workflow/rilis belum dijalankan di GitHub. Tes unit menguji konfigurasi, versi, URL, checksum, dan logika pilihan shortcut termasuk shortcut keluar; tes tidak membuktikan bahwa OS menyampaikan atau memblokir tombol. GUI, hook Windows, login, build, pemasangan ulang otomatis, dan perilaku kiosk perlu diuji pada tiap platform sebenarnya sebelum produksi. Tes build Linux di lingkungan terbatas mungkin kekurangan pustaka desktop sistem; workflow menginstal dependensi Linux pada runner.
