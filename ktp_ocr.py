"""
ktp_ocr.py — Server OCR KTP (baca NIK, Nama, Tempat/Tgl Lahir). GRATIS (EasyOCR).

Jalankan:
    pip install easyocr flask flask-cors opencv-python pillow-heif
    python ktp_ocr.py
Endpoint:  POST http://127.0.0.1:5001/ocr-ktp   (form-data: file=<gambar KTP>)
"""

import os, re, math, statistics

OCR_ENGINE = os.environ.get("OCR_ENGINE", "easy").lower()

# ======================================================================
# PARSER
# ======================================================================

_MAP = str.maketrans({"O":"0","Q":"0","D":"0","I":"1","L":"1","|":"1",
                      "S":"5","B":"8","Z":"2"})

def _bersih(s):
    return re.sub(r"\s+", " ", str(s)).strip()

def _tok_digit(tok):
    return re.sub(r"\D", "", tok.upper().translate(_MAP))

def _ambil_nik(lines):
    for l in lines:                                  # 1) token tunggal 16 digit
        for tok in l.split():
            c = _tok_digit(tok)
            if len(c) == 16:
                return c
    for l in lines:                                  # 2) baris ber-'NIK'
        if re.search(r"N[I1L]K", l.upper()):
            gab = "".join(_tok_digit(t) for t in l.split() if len(_tok_digit(t)) >= 4)
            m = re.search(r"\d{16}", gab)
            if m:
                return m.group(0)
    for l in lines:                                  # 3) global 16 digit beruntun
        gab = "".join(_tok_digit(t) for t in l.split() if len(_tok_digit(t)) >= 4)
        m = re.search(r"\d{16}", gab)
        if m:
            return m.group(0)
    return None

def _cari_tanggal(teks):
    """Terima aneka format: 25-11-2007, 25/11/2007, 2511-2007, 25112007, dst."""
    for m in re.finditer(r"\d[\d\s.\-/]{5,12}\d", teks):
        d = re.sub(r"\D", "", m.group(0))
        for i in range(0, max(1, len(d) - 7)):
            seg = d[i:i + 8]
            if len(seg) < 8:
                break
            dd, mm, yy = seg[:2], seg[2:4], seg[4:]
            if 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12 and 1900 <= int(yy) <= 2099:
                return "%s-%s-%s" % (dd, mm, yy)
    return None

def _tempat_tgl(lines):
    for l in lines:
        if "LAHIR" in l.upper():
            tgl = _cari_tanggal(l)
            after = re.sub(r"(?i)^.*?lahir[\s:]*", "", l)     # buang label
            mt = re.match(r"([A-Za-z]+(?:\s+[A-Za-z]+){0,3})", after)
            tempat = mt.group(1).strip() if mt else None
            if tempat and tempat.upper().replace("-", "") in ("LAKI", "LAKILAKI"):
                tempat = None                                  # kejebak kolom lain
            return tempat, tgl
    return None, _cari_tanggal(" ".join(lines))

_PROV = {"11","12","13","14","15","16","17","18","19","21",
         "31","32","33","34","35","36","51","52","53",
         "61","62","63","64","65","71","72","73","74","75","76",
         "81","82","91","92","93","94","95","96"}

def _nik_valid(nik):
    """NIK sah: 16 digit, kode provinsi ada, tanggal lahir (digit 7-12) masuk akal.
    Menangkap salah baca kotor (mis. kode provinsi '48' yang tidak ada)."""
    if not nik or len(nik) != 16 or not nik.isdigit():
        return False
    if nik[:2] not in _PROV:
        return False
    dd = int(nik[6:8]); mm = int(nik[8:10])
    if dd > 40:                       # perempuan: tanggal + 40
        dd -= 40
    return 1 <= dd <= 31 and 1 <= mm <= 12

def _nama_valid(n):
    """Nama sah: mayoritas huruf, tanpa karakter aneh (';', angka) hasil salah baca."""
    if not n:
        return False
    huruf = sum(c.isalpha() for c in n)
    aneh = sum(1 for c in n if not (c.isalpha() or c in " .,'-"))
    return huruf >= 3 and aneh == 0

def parse_ktp_lines(lines):
    lines = [_bersih(l) for l in lines if _bersih(l)]
    hasil = {"nik": None, "nama": None, "tempat_lahir": None,
             "tgl_lahir": None, "status": "perlu_ulang", "masalah": []}

    hasil["nik"] = _ambil_nik(lines)

    for l in lines:                                  # Nama (hindari baris berisi NIK)
        up = l.upper()
        if ("NAMA" in up) and not re.search(r"\d{6,}", l):
            val = re.sub(r"(?i)^.*?nama\s*:?\s*", "", l).strip()
            if val:
                hasil["nama"] = val
            break

    tempat, tgl = _tempat_tgl(lines)
    hasil["tempat_lahir"] = tempat
    hasil["tgl_lahir"] = tgl

    if not _nik_valid(hasil["nik"]):
        hasil["masalah"].append("NIK tidak terbaca jelas / tidak valid")
    if not _nama_valid(hasil["nama"]):
        hasil["masalah"].append("Nama tidak terbaca jelas")
    if not hasil["masalah"]:
        hasil["status"] = "ok"
    return hasil

# ======================================================================
# GAMBAR: orientasi, luruskan, susun baris
# ======================================================================

def _median_angle(boxes):
    angs = []
    for box, teks, conf in boxes:
        (x0, y0), (x1, y1) = box[0], box[1]
        angs.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    return statistics.median(angs) if angs else 0.0

def _rotate(img, ang):
    import cv2
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), ang, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def _rot90(img, deg):
    import cv2
    if deg == 90:  return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if deg == 180: return cv2.rotate(img, cv2.ROTATE_180)
    if deg == 270: return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img

def _susun_baris(boxes, tol=16):
    items = []
    for box, teks, conf in boxes:
        ys = [p[1] for p in box]; xs = [p[0] for p in box]
        items.append((sum(ys) / 4.0, sum(xs) / 4.0, teks))
    items.sort(key=lambda t: t[0])
    baris, cur, ref = [], [], None
    for yc, xc, teks in items:
        if ref is None or abs(yc - ref) <= tol:
            cur.append((xc, teks)); ref = yc if ref is None else (ref + yc) / 2
        else:
            cur.sort(key=lambda t: t[0]); baris.append(" ".join(t[1] for t in cur))
            cur = [(xc, teks)]; ref = yc
    if cur:
        cur.sort(key=lambda t: t[0]); baris.append(" ".join(t[1] for t in cur))
    return baris

# ======================================================================
# MESIN OCR
# ======================================================================

_easy = None
def _get_easy():
    global _easy
    if _easy is None:
        import easyocr
        _easy = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _easy

def _resize_ocr(img):
    """Ukuran ideal untuk OCR: foto besar dikecilkan (cepat), foto kecil diperbesar (kebaca)."""
    import cv2
    h, w = img.shape[:2]
    m = max(h, w)
    if m > 1600:
        s = 1600.0 / m
        return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    if m < 1000:
        s = 1400.0 / m
        return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC)
    return img

def _lines_easy(img):
    reader = _get_easy()
    img = _resize_ocr(img)
    boxes = reader.readtext(img, detail=1)
    ang = _median_angle(boxes)
    if abs(ang) >= 3:                                 # luruskan hanya jika miring nyata
        boxes = reader.readtext(_rotate(img, ang), detail=1)
    return _susun_baris(boxes)

_paddle = None
def _paddle_boxes(engine, img):
    """Jalankan PaddleOCR, kembalikan daftar (box, teks, conf) — tahan beda versi."""
    out = engine.ocr(img, cls=True)
    boxes = []
    def walk(x):
        # bentuk satu item: [ box(4 titik), (teks, conf) ]
        if (isinstance(x, list) and len(x) == 2 and isinstance(x[0], list)
                and len(x[0]) == 4 and isinstance(x[1], (list, tuple))
                and len(x[1]) >= 1 and isinstance(x[1][0], str)):
            conf = x[1][1] if len(x[1]) > 1 else 0.9
            boxes.append((x[0], x[1][0], conf))
            return
        if isinstance(x, list):
            for y in x:
                if y is not None:
                    walk(y)
    if out:
        walk(out)
    return boxes

def _lines_paddle(img):
    global _paddle
    if _paddle is None:
        from paddleocr import PaddleOCR
        _paddle = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    img = _resize_ocr(img)
    boxes = _paddle_boxes(_paddle, img)
    ang = _median_angle(boxes)
    if abs(ang) >= 3:                                 # luruskan hanya jika miring nyata
        boxes = _paddle_boxes(_paddle, _rotate(img, ang))
    return _susun_baris(boxes)

def _lines_tesseract(img):
    import pytesseract, cv2
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape[:2]
    if w < 1400:
        s = 1400.0 / w
        g = cv2.resize(g, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC)
    return [l for l in pytesseract.image_to_string(g, lang=os.environ.get("TESS_LANG", "eng")).splitlines() if l.strip()]

def _ocr_lines(img):
    """Pilih mesin; kalau library tak terpasang, otomatis pindah ke yang ada."""
    for eng in [OCR_ENGINE] + [e for e in ("easy", "tesseract", "paddle") if e != OCR_ENGINE]:
        try:
            if eng == "paddle":      return _lines_paddle(img)
            elif eng == "tesseract": return _lines_tesseract(img)
            else:                    return _lines_easy(img)
        except (ImportError, ModuleNotFoundError):
            continue
    raise RuntimeError("tidak ada mesin OCR yang terpasang")

def baca_ktp(img):
    lines = _ocr_lines(img)
    hasil = parse_ktp_lines(lines)
    if _nik_valid(hasil["nik"]):
        return hasil
    # Banyak teks terbaca tapi NIK tetap tidak valid = masalah kualitas/aus,
    # bukan orientasi. Diputar-putar tak menolong -> langsung kembalikan (cepat).
    if len(lines) >= 5:
        return hasil
    # Teks sedikit -> foto mungkin terputar. Coba orientasi lain.
    for deg in (90, 180, 270):
        h2 = parse_ktp_lines(_ocr_lines(_rot90(img, deg)))
        if _nik_valid(h2["nik"]):
            return h2
    return hasil

# ======================================================================
# SERVER
# ======================================================================

def buat_app():
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import numpy as np, cv2

    app = Flask(__name__)
    CORS(app)

    def _decode(file_bytes):
        # PIL + exif_transpose: perbaiki orientasi foto HP (EXIF) & dukung HEIC.
        from io import BytesIO
        from PIL import Image, ImageOps
        try:
            import pillow_heif; pillow_heif.register_heif_opener()
        except Exception:
            pass
        im = Image.open(BytesIO(file_bytes))
        im = ImageOps.exif_transpose(im)              # <- kunci: luruskan sesuai EXIF
        im = im.convert("RGB")
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

    @app.route("/ocr-ktp", methods=["POST"])
    def ocr_ktp():
        f = request.files.get("file")
        if not f:
            return jsonify({"status": "perlu_ulang", "masalah": ["tidak ada file"]}), 400
        try:
            img = _decode(f.read())
        except Exception as e:
            return jsonify({"status": "perlu_ulang", "masalah": ["gambar tidak bisa dibaca: " + str(e)]}), 400
        try:
            return jsonify(baca_ktp(img))
        except Exception as e:
            return jsonify({"status": "perlu_ulang", "masalah": ["gagal memproses: " + str(e)]}), 500

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "engine": OCR_ENGINE})

    return app

def _warm():
    """Panaskan model sekali saat start biar upload pertama tidak lemot."""
    try:
        import numpy as np
        _ocr_lines(np.zeros((80, 240, 3), dtype=np.uint8))
    except Exception:
        pass

if __name__ == "__main__":
    eng = OCR_ENGINE
    if eng == "paddle":
        try:
            import paddleocr  # cek apakah PaddleOCR terpasang
        except Exception:
            print("!! PaddleOCR belum terpasang — server sementara pakai EasyOCR.")
            print("!! Pasang dulu:  pip install paddleocr paddlepaddle")
            eng = "easy (fallback)"
    print("=" * 48)
    print("  SERVER OCR KTP  |  mesin:", eng.upper())
    print("  Memanaskan model… (sebentar, sekali saja)")
    _warm()
    print("  Siap. Buka http://127.0.0.1:5001  (biarkan jendela ini)")
    print("=" * 48)
    buat_app().run(host="127.0.0.1", port=5001, debug=False)
