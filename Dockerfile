FROM 533267185808.dkr.ecr.us-west-2.amazonaws.com/docker.io/central/library/node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM 533267185808.dkr.ecr.us-west-2.amazonaws.com/docker.io/central/library/python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GENE2IMAGE_FRONTEND_DIR=/app/frontend/dist \
    GENE2IMAGE_DATA_DIR=/data \
    PORT=8000
# The Thisse image index is baked into /data at build time (see below), so
# GENE2IMAGE_DATA_DIR has an in-image default and no runtime volume is needed.

RUN pip install --no-cache-dir uv

# Install third-party deps first from the lock so this layer stays cached
# until uv.lock changes. uv export honors the lock (uv pip install . would not,
# it re-resolves from pyproject.toml); the pinned requirements give reproducible
# builds. Source is copied afterward so edits don't bust the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt

# Bake the Thisse image index into /data. The extractor downloads the ZFIN
# TSVs, joins them, and writes image_metadata.json. Done at build time so the
# container is self-contained — no runtime data volume to mount; refresh the
# data by rebuilding. Placed before the source COPY so backend edits don't bust
# this (network-bound) layer. Intermediate TSVs and the unused .tsv export and
# the build-only extractor are removed to keep the layer small.
# --min-records gates the bake: a truncated download or drifted ZFIN file format
# can parse into an empty/partial index that would otherwise ship silently (the
# app starts healthy but every gene query returns empty). The Thisse set is ~53k
# records, so a 10k floor fails the build on corruption with ample headroom.
COPY zfin_image_metadata_extractor.py ./
RUN mkdir -p /data \
    && python zfin_image_metadata_extractor.py \
        --input-dir /tmp/zfin_data \
        --output-prefix /data/image_metadata \
        --min-records 10000 \
    && rm -rf /tmp/zfin_data /data/image_metadata.tsv zfin_image_metadata_extractor.py

# Then copy source and install only the local package; deps already installed.
COPY backend/ ./backend/
RUN uv pip install --system --no-cache --no-deps .

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Drop root: run as a non-privileged user. The app only reads /app and /data
# (baked in at build time), and binds the non-privileged port 8000, so no root
# capability is needed at runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec uvicorn gene2image.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
