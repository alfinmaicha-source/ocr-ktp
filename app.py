import os

# Mesin OCR: Tesseract (ringan, muat di hosting gratis 512MB).
os.environ.setdefault("OCR_ENGINE", "tesseract")
os.environ.setdefault("TESS_LANG", "ind+eng")

from ktp_ocr import buat_app, _warm

# buat_app() sudah: Flask + CORS(semua origin) + route /ocr-ktp + /health
app = buat_app()


@app.route("/")
def home():
    return (
        "<h3>Server OCR KTP aktif ✅</h3>"
        "<p>Kirim gambar KTP lewat <code>POST /ocr-ktp</code> (form-data, field <code>file</code>).</p>"
        "<p>Cek status: <a href='/health'>/health</a></p>"
    )


# Panaskan sekali saat worker boot.
try:
    _warm()
except Exception:
    pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, threaded=True)
