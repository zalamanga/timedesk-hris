# Panduan demo dan interview

## Penjelasan satu menit

TimeDesk adalah proyek HRIS untuk pencatatan waktu kerja. Karyawan mencatat masuk/pulang dari akun sendiri, sedangkan backend memberikan timestamp UTC. React menampilkan waktu dalam WIB. Jika ada kesalahan, karyawan mengusulkan koreksi, dan manajer langsung memeriksa interval serta alasannya. Persetujuan memperbarui interval dan audit dalam satu transaksi. PostgreSQL menjaga satu sesi aktif per karyawan, termasuk ketika permintaan datang bersamaan.

## Demo lima langkah

1. Jalankan `scripts/Start.ps1`, buka port 8095, ambil sandi privat dari `.local/LOCAL-CREDENTIALS.txt`.
2. Masuk `employee@timedesk.test`. Tunjukkan banner Training, tombol masuk/pulang, filter tanggal dan sesi contoh melewati tengah malam.
3. Ajukan koreksi pada sesi selesai. Jelaskan bahwa interval asli belum berubah. Bila sudah ada koreksi pending, gunakan sesi lain atau tunjukkan koreksi contoh.
4. Keluar dan masuk `manager@timedesk.test`. Pilih Koreksi waktu → Tim langsung. Bandingkan waktu, baca alasan, lalu putuskan. Penolakan memerlukan alasan minimal 10 karakter.
5. Buka rekap dan CSV. Jelaskan pemotongan durasi pada batas hari WIB serta pemisahan durasi aktif dari total selesai.

## Pertanyaan yang sering muncul

**Mengapa waktu dari server?** Agar clock-in/out tidak mempercayai field timestamp dari browser. Ini tidak membuktikan lokasi fisik atau identitas biometrik; batas tersebut ditulis di README.

**Bagaimana mencegah dua sesi aktif?** API mengunci baris User per karyawan. PostgreSQL juga memiliki partial unique index untuk baris yang `end_at IS NULL`. Constraint tetap menjaga invariant bila ada jalur penulisan lain.

**Bagaimana bila jaringan putus setelah masuk tercatat?** Frontend menggunakan UUID intent yang sama untuk retry. Backend mengembalikan entry yang sudah ada tanpa menambah event, bahkan jika entry itu sudah selesai.

**Apa beda idempotency dan optimistic version?** UUID mengidentifikasi perintah clock-in yang sama. Versi menyatakan state yang dilihat pengguna ketika mengubah data. Keduanya menangani masalah berbeda: retry akibat jaringan dan konflik akibat state berubah.

**Mengapa perlu row lock dan versi?** Lock menserialisasi transaksi bersamaan di server; versi menolak keputusan berdasarkan layar lama. Lock sendiri tidak memberi tahu apakah pengguna membaca versi terbaru sebelum menekan tombol.

**Bagaimana menjaga privasi?** Semua daftar dan aggregate menggunakan ID diri sendiri atau bawahan langsung. Pengguna di luar cakupan mendapat 404 untuk detail. Alasan koreksi hanya ada pada endpoint koreksi yang dibatasi, tidak dimasukkan ke CSV/rekap.

**Apa yang terjadi jika audit gagal?** Seluruh transaksi dibatalkan. Tes menyuntikkan kegagalan insert audit dan memeriksa interval serta status koreksi tetap semula.

**Mengapa tidak ada payroll?** Portfolio ini memisahkan pencatatan teknis dan perhitungan upah. Payroll membutuhkan aturan organisasi, jadwal, libur, break, komponen penghasilan dan validasi yang belum disediakan proyek.

**Apa tes pentingnya?** Periksa `docs/VERIFICATION.md` untuk hasil aktual. Fokus pada retry UUID, dua transaksi bersamaan di PostgreSQL, batas data tim, interval bersebelahan, cross-midnight clipping dan rollback audit. SQLite tidak cukup untuk membuktikan `SELECT FOR UPDATE`.

## Bagian kode untuk ditunjukkan

- `models.py`: partial indexes dan versi.
- `main.py`: `lock_employee`, `check_in`, `decide`, `scope_ids`, `recap`.
- `intervals.py`: batas WIB dan clipping.
- `test_attendance.py`: uji race, privasi dan rollback.
- `App.tsx`: menyimpan draft saat 409 dan mencegah mutasi selama reload.

Jelaskan batas proyek secara langsung. Jangan mengklaim pengguna perusahaan, data absensi nyata, lokasi GPS, audit compliance, ataupun payroll yang tidak diimplementasikan.
