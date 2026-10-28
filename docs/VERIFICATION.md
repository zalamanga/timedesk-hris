# Verifikasi TimeDesk

Hasil aktual pada 28 Oktober 2026:

| Pemeriksaan | Hasil |
| --- | --- |
| `scripts/Test.ps1`, PostgreSQL 17 terisolasi | **68 lulus**, tanpa skip |
| Vitest 4.1.12 | **4 lulus** |
| TypeScript/Vite production build | Lulus pada host dan image Linux |
| Playwright Edge pada stack Docker | **10 lulus** |
| Screenshot aplikasi nyata | Tiga desktop 1440×1000 dan satu mobile 390×844 |
| Kontras/reflow DOM | Login serta workspace karyawan/manajer pada 320/390/768/1024/1440 px |

## Cakupan pengujian

- Backend API: timestamp server, UUID retry, satu sesi aktif, versi checkout, koreksi approve/reject/withdraw, input invalid, privasi detail/list/count/export, CSRF/Origin, kedaluwarsa sesi, login limiter, CSV formula escaping.
- Rekap: pembagian interval tengah malam WIB, clipping rentang dan pemisahan durasi aktif.
- Integritas: partial unique index, satu pending correction, stale snapshot, tabrakan yang muncul setelah pengajuan dan rollback jika insert audit gagal.
- Riwayat koreksi: snapshot waktu asli tetap tersimpan setelah persetujuan dan koreksi berikutnya; audit menyertakan timestamp sebelum/sesudah.
- Batas laporan: tahun 2000-2200, tanggal overflow, cap tim dan entry, narrowing employee_id sebelum cap, serta konsistensi batas rekap/CSV.
- Validasi identitas: Login dan CLI memakai validator bentuk email yang sama; alamat tidak lengkap tidak membuat akun.
- PostgreSQL concurrency: dua clock-in dengan UUID sama, dua UUID berbeda dan dua persetujuan koreksi dengan versi sama.
- Operasional: Alembic upgrade awal/berulang, seed satu kali, sandi tidak direset, seed gagal atomik dan interval tidak di masa depan.
- Frontend: formatter WIB, durasi melebihi 24 jam dan tanggal lokal.
- Browser: masuk/pulang, cakupan tim, koreksi, penyimpanan draft pada 409, ekspor, rentang invalid, layout 320/390 dan keyboard focus. Capture menulis empat gambar dari data Training.

## Perintah

```powershell
python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
npm run test:e2e
```

Tes backend default menggunakan SQLite sementara; tiga tes locking hanya dijalankan bila `APP_TEST_DATABASE_URL` berisi URL PostgreSQL test terpisah. Fixture sengaja menolak nama database tanpa kata `test` untuk mengurangi risiko salah sasaran. Semua tabel pada database test dibuat ulang; tidak menggunakan database demo.

## Hasil aktual

Ketiga race PostgreSQL dijalankan: UUID yang sama mengembalikan satu entry; UUID berbeda menghasilkan satu sesi aktif; dua persetujuan dengan versi sama menghasilkan satu pemenang. Tes lain memeriksa rollback audit, overlap, clipping, batas laporan dan pelestarian timestamp asli.

Browser menjalankan catat masuk/pulang, pengajuan dan persetujuan koreksi, privasi tim, CSV, validasi rentang, fokus dan reflow. Kasus draf memakai respons 409 yang disimulasikan melalui route Playwright; konflik versi database yang nyata diperiksa terpisah di backend PostgreSQL. Empat PNG diperiksa langsung sesudah capture.

Workflow [GitHub Actions](https://github.com/zalamanga/timedesk-hris/actions) menjalankan backend, frontend dan seluruh kasus browser pada checkout serta database baru. [Gate tampilan](UX-REVIEW.md) mencatat review akhir. Satu peringatan deprecation berasal dari adaptor TestClient FastAPI/Starlette ke httpx; seluruh tes tetap lulus.

## Batas bukti

Tes tidak membuktikan compliance ketenagakerjaan, validitas identitas fisik, ketersediaan produksi, volume enterprise, atau perlindungan dari seluruh jenis serangan. Tes browser memakai dataset Training dan satu browser engine. Pengujian race PostgreSQL membuktikan skenario perintah paralel yang disebutkan, bukan seluruh kemungkinan kegagalan jaringan/database.
