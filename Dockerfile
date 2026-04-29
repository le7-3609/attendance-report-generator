# Pin to Debian bookworm to keep apt package names stable.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ATTENDANCE_FONTS_DIR=/app/fonts \
    TESSDATA_PREFIX=/app/tessdata

WORKDIR /app

# System deps:
# - Tesseract + Hebrew language pack (OCR)
# - Poppler (PDF text/images utilities used by pdfplumber OCR fallback paths)
# - Common PDF/image runtime libs (Pillow/pypdfium2)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-heb \
      poppler-utils \
      libpoppler-cpp0v5 \
      liblept5 \
      libglib2.0-0 \
      libjpeg62-turbo \
      zlib1g \
      libpng16-16 \
      libtiff6 \
      libopenjp2-7 \
      libfreetype6 \
      liblcms2-2 \
      libwebp7 \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY fonts ./fonts
COPY tessdata ./tessdata

# (Optional) keep repo-root templates for local dev parity; package uses src/templates.
COPY templates ./templates

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir .

ENTRYPOINT ["attendance-report"]
