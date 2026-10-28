# Panduan file dan fungsi

## Backend

| File | Fungsi dan alasan pemisahan |
| --- | --- |
| `app/config.py` | `Settings` membaca environment; menolak wildcard origin dan batas negatif |
| `app/db.py` | `Database` menyiapkan engine dan session factory; SQLite menyalakan foreign keys |
| `app/models.py` | Skema SQLAlchemy, constraints, partial indexes, UTCDateTime; timestamp tanpa zona ditolak |
| `app/schemas.py` | Payload strict: field tambahan ditolak, UUID masuk, versi positif dan interval koreksi |
| `app/security.py` | Argon2, token acak dan SHA-256 token; dummy hash menyamakan jalur verifikasi akun tidak ditemukan |
| `app/intervals.py` | `window`, `clip_seconds`, `hhmm`, `iso`; aturan WIB dan durasi tidak bercampur dengan route |
| `app/main.py` | Factory, auth, filtering, lock, transaksi attendance/correction, rekap dan CSV |
| `app/seed.py` | Dataset Training satu kali; advisory transaction lock PostgreSQL dan marker atomik |
| `app/cli.py` | `init-db`, `seed-demo`, `create-user`; sandi dari environment, tidak lewat argumen |
| `alembic/versions/0001_initial.py` | DDL awal yang terekam; upgrade berulang berhenti pada revision terbaru |

### Membaca `main.py`

1. `get_db` membuka satu ORM session per request; transaksi yang tidak commit dibatalkan ketika session ditutup.
2. `get_auth` mengambil cookie, menghitung hash, membaca sesi, memeriksa kedaluwarsa/status pengguna. `mutation_auth` menambahkan validasi CSRF.
3. `scope_ids` menghasilkan ID yang boleh dibaca untuk mode `mine` atau `team`. `readable` menerapkan aturan yang sama pada satu record.
4. `lock_employee` selalu didahulukan sebelum lock entry/koreksi. `lock_entry` memastikan kepemilikan/cakupan sebelum mutasi.
5. `require_version` menolak draft lama. `has_overlap` memeriksa interval half-open. `audit` menambahkan event tanpa melakukan commit terpisah. Koreksi menyimpan `original_start` dan `original_end` saat pengajuan, sehingga riwayat tetap menunjukkan interval yang ditinjau meskipun entry kemudian berubah. Event persetujuan juga merekam timestamp sebelum/sesudah secara tepat.
6. `commit` menangani pelanggaran constraint sebagai 409. Kegagalan transaksi tidak disamarkan sebagai keberhasilan.
7. `create_app` memasang middleware, route auth, clock-in/out, koreksi, rekap dan ekspor. Jam berasal dari dependency `clock`.

### Kontrak API ringkas

| Endpoint | Input/hasil utama |
| --- | --- |
| `POST /api/auth/login` | email+sandi → user, CSRF, demo flag dan cookie |
| `GET /api/auth/me` | sesi berjalan → identitas dan CSRF |
| `POST /api/auth/logout` | CSRF → hapus sesi dan cookie |
| `GET /api/team` | manajer → bawahan langsung aktif; optional employee_id untuk mempersempit |
| `GET /api/attendance` | `from_date`, `to_date`, `scope`, opsional `employee_id`; daftar, sesi sendiri aktif, jam server |
| `POST /api/attendance/check-in` | `{request_id: UUID}` → 201 baru atau 200 retry |
| `POST /api/attendance/{id}/check-out` | `{expected_version}` → sesi selesai |
| `GET /api/attendance/{id}` | entry dan audit yang dapat dibaca |
| `POST /api/attendance/{id}/corrections` | versi entry, proposed_start/end berzona dan reason; server mengisi original_start/end dari entry |
| `GET /api/corrections` | `scope`, `state`, optional `employee_id`; daftar maksimal 200 dan total |
| `GET /api/corrections/{id}` | detail koreksi termasuk alasan, snapshot interval asli dan usulan bila berhak |
| `POST /api/corrections/{id}/approve` | versi koreksi dan optional note |
| `POST /api/corrections/{id}/reject` | versi koreksi dan note minimal 10 karakter |
| `POST /api/corrections/{id}/withdraw` | versi koreksi; pemilik pending saja |
| `GET /api/recap` | rentang/cakupan → durasi selesai per hari dan durasi aktif terpisah |
| `GET /api/attendance/export.csv` | filter yang sama → interval WIB, detik terpotong pada rentang, tanpa alasan koreksi |

Contoh clock-in setelah login:

```json
{"request_id":"24555f56-5d24-4ebf-9ea3-9825f86e25ea"}
```

UUID contoh hanya menunjukkan format. Buat UUID baru untuk niat masuk baru dan gunakan UUID yang sama ketika mengulang permintaan yang hasilnya belum diketahui. Jangan menambah `start_at` atau `employee_id`; server menolaknya.

## Frontend

`src/api.ts` mendefinisikan tipe respons dan satu wrapper fetch. `ApiError.status` membedakan 401, 409 dan error lain. Cookie dikirim ke origin yang sama, sementara CSRF ditambahkan hanya untuk mutasi.

`src/App.tsx` memuat sesi, formulir login dan workspace. Data attendance/corrections/recap dimuat bersama. Generation counter mencegah respons filter lama menimpa tampilan baru. Clock elapsed menggunakan offset jam server untuk display, bukan timestamp input backend. Riwayat koreksi membandingkan snapshot **Catatan saat diajukan** dengan usulan, bukan mengganti interval asli yang ditampilkan setelah persetujuan.

Rentang tanggal dibatasi pada tahun 2000-2200 dan maksimal 31 hari. Cakupan tim dibatasi 500 karyawan; parameter `employee_id` dapat mempersempit tim sebelum batas diterapkan. Rekap dan CSV memakai batas 10.000 entry yang sama setelah filtering. Kelebihan batas mengembalikan 422, bukan hasil terpotong yang tampak lengkap.

UUID clock-in disimpan dalam ref sampai keberhasilan diketahui. Kesalahan jaringan tidak langsung membuat UUID baru. Ketika 409 terjadi, mutasi dinonaktifkan sampai **Muat ulang**, sementara draf koreksi dan note keputusan disimpan. Saat memuat ulang, versi entry yang ditemukan diperbarui tanpa menghapus teks draf.

Tampilan memakai tiga area kerja: Kehadiran, Koreksi waktu, Rekap harian. Manajer memiliki cakupan Saya/Tim langsung. Tidak ada kontrol untuk clock-out orang lain, edit interval langsung, atau melihat alasan di rekap.

`src/styles.css` mengubah tabel menjadi baris berlabel pada layar kecil. Kontrol tidak bergantung pada hover, fokus terlihat, form memiliki label, dan status memiliki teks selain warna. `src/api.test.ts` memeriksa format WIB dan durasi lintas 24 jam.

## Mengubah fitur dengan aman

Untuk menambah break atau jadwal shift, tentukan dahulu apakah durasi dihitung sebagai interval terpisah atau dikurangi dari sesi. Jangan hanya mengurangi angka pada UI: query rekap, CSV, koreksi, constraints dan tes lintas tengah malam harus menggunakan aturan yang sama. Untuk deployment multi-organisasi, tambahkan tenant scope pada seluruh query dan constraint, kemudian uji kebocoran lintas tenant.
