FROM python:3.11-slim

# Tesseract OCR (mesin) + bahasa Indonesia & Inggris + library OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ind \
        tesseract-ocr-eng \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    OCR_ENGINE=tesseract \
    TESS_LANG=ind+eng \
    PORT=7860

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

# Bind ke $PORT (Render set otomatis; lokal default 7860). Shell form biar $PORT kebaca.
CMD gunicorn -b 0.0.0.0:${PORT:-7860} -w 1 --threads 2 -t 120 app:app
