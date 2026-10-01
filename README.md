# Server OCR KTP — Beli Gas Subsidi 3 Kg

Server pembaca KTP (NIK, nama, tempat/tanggal lahir) untuk form registrasi.
Flask + Tesseract OCR (ringan, muat di hosting gratis 512MB). Dipanggil web lewat `POST /ocr-ktp`.

## Endpoint
- `GET /` — halaman status
- `GET /health` — cek server hidup
- `POST /ocr-ktp` — kirim gambar KTP (form-data, field `file`), balikannya JSON:
  `{status, nik, nama, tempat_lahir, tgl_lahir, masalah[]}`

## Deploy (Render, gratis)
Docker otomatis kebaca dari `Dockerfile`. Server bind ke `$PORT` (diset Render otomatis).

## Catatan
- Hosting gratis "tidur" saat idle; request pertama ~1 menit untuk bangun. Sesudah itu cepat.
- OCR tidak 100% akurat; KTP buram/aus bisa gagal — ditangani di sisi web (fallback daftar manual).
