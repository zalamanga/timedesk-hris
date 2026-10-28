# Gate tampilan TimeDesk

**PASS**, ditinjau langsung oleh root pada 28 Oktober 2026 setelah build Docker, sepuluh kasus browser dan inspeksi empat PNG. Bukti: [VERIFICATION.md](VERIFICATION.md), `e2e/99-accessibility.spec.ts`, `e2e/attendance.spec.ts`, `screenshots/` dan [arah tampilan](../DESIGN.md).

- R-01 PASS: warna solid tanpa gradient/glow dekoratif.
- R-02 PASS: source UI dan dokumentasi diperiksa; tidak ada em dash.
- R-03 PASS: login serta dua workspace tidak meluap pada 320/390/768/1024/1440 px; baris tabel menjadi catatan berlabel di mobile.
- R-04 PASS: interval dan angka durasi menyampaikan data kerja, tanpa paket ikon pengisi.
- R-05 PASS: kontrol sesi, riwayat, perbandingan koreksi dan rekap mengikuti tugas masing-masing.
- R-06 PASS: Arial lokal dan angka tabular mempunyai alasan keterbacaan pada DESIGN.md.
- R-07 PASS: grid hanya menyusun interval/tabel, bukan pola latar dekoratif.
- R-08 PASS: panah memisahkan awal/akhir interval, bukan dekorasi pada setiap tombol.
- R-09 PASS: label pending/approved/active menunjukkan state database; tidak ada badge pemasaran.
- R-10 PASS: panel solid tanpa glassmorphism.
- R-11 PASS: radius kecil pada kontrol dan panel; bukan semua elemen berbentuk pill.
- R-12 PASS: batas memisahkan catatan; tidak ada shadow besar pada seluruh komponen.
- R-13 PASS: status dan fokus tidak memakai glow.
- R-14 PASS: clock strip, tabel dan perbandingan waktu mempunyai ukuran sesuai isi.
- R-15 PASS: Catat masuk, Catat pulang, Ajukan koreksi dan Unduh CSV menyebut tindakan.
- R-16 PASS: copy menjelaskan pencatatan waktu dan review, tanpa klaim pemasaran generik.
- R-17 PASS: interval, detik, total dan jumlah koreksi berasal dari API/database.
- R-18 PASS: tidak ada testimonial atau pelanggan fiktif.
- R-19 PASS: penghitung sesi memperbarui teks waktu sebagai data; tidak ada animasi dekoratif berulang.
- R-20 PASS: aksi sesi sendiri dan perbandingan interval menjadi fokus, bukan grafik dashboard pengisi.
- R-21 PASS: tema terang mengikuti pilihan pengguna; tidak ada toggle tema yang belum selesai.
- R-22 PASS: tidak ada ilustrasi generik; catatan waktu merupakan visual utama.
- R-23 PASS: wordmark teks dan screenshot runtime; seluruh akun/data awal diberi label Training.
- R-24 PASS: navigasi Kehadiran, Koreksi waktu dan Rekap harian membuka tampilan nyata.
- R-25 PASS: tes DOM memeriksa teks/placeholder ≥4,5:1 dan batas input ≥3:1; pasangan warna dicatat pada DESIGN.md.
- R-26 PASS: kontrol terhubung ke API; sesi, pengajuan/approval koreksi, filter, CSV dan logout diverifikasi.
- R-27 PASS: loading, empty, rentang invalid, sesi berakhir dan konflik mempunyai pesan serta langkah lanjut.
- R-28 PASS: tidak ada FAQ pengisi.
- R-29 PASS: dasar netral, aksen slate blue dan warna status dengan makna tertulis.
- R-30 PASS: komposisi berasal dari pekerjaan absensi, bukan penyalinan produk lain.
- R-31 PASS: clock mendapat bobot terbesar; interval asli/usulan berdampingan agar keputusan bisa diperiksa.
- R-32 PASS: kontrol native, label, fokus terlihat dan perpindahan keyboard diperiksa pada 320/390 px.
- R-33 PASS: UI tertulis pada source React/CSS; tidak ada patch DOM atau CSS saat runtime.
- R-34 PASS: tema terang diperiksa pada karyawan/manajer, koreksi dan rekap.
- R-35 PASS: build dijalankan dan click-through tiga navigasi, pencatatan, koreksi, filter serta CSV tercatat di browser.
- R-36 PASS: prototipe tidak mengklaim payroll, biometrik, kepatuhan atau keamanan mutlak.
- R-37 PASS: arah terang/rapi dengan ENERGY 1 / RHYTHM 2 / MOTION 1 dinyatakan sebelum pembuatan.
- R-38 PASS: banner Training menjelaskan bahwa identitas, interval awal dan alasan contoh bersifat sintetis.

- Dials PASS: ENERGY 1 pada permukaan solid, RHYTHM 2 pada clock/tabel/perbandingan, MOTION 1 tanpa dekorasi bergerak.
- Focal point PASS: satu tindakan sesi untuk karyawan; waktu asli/usulan untuk reviewer.
- Whitespace PASS: jarak memisahkan kontrol sesi dari laporan dan alasan koreksi.
- Accent PASS: slate blue menandai navigasi serta aksi utama.
- Identity PASS: waktu WIB, angka tabular dan pasangan interval menghubungkan seluruh layar.
- Design Read PASS: pilihan aplikasi kerja terang dari pengguna menjadi arah tertulis.
- C-1 PASS: warna, font dan urutan konten mempunyai alasan pada DESIGN.md.
- C-2 PASS: tindakan tersambung ke backend; alasan minimum, loading dan konflik menonaktifkan perubahan dengan penjelasan.
- C-3 PASS: setiap bagian mendukung pencatatan, pemeriksaan atau koreksi waktu.
- C-4 PASS: lima lebar layar, keyboard, error, empty, scoped data dan konflik diperiksa.
- C-5 PASS: angka berasal dari database, snapshot waktu asli dipertahankan dan screenshot berasal dari runtime.

Gate ini memeriksa alur yang dicatat, bukan sertifikasi aksesibilitas menyeluruh.
