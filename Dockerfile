FROM 533267185808.dkr.ecr.us-west-2.amazonaws.com/docker.io/central/library/node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Bake the Thisse image index in a dedicated build stage. The extractor needs
# the heavy build-only deps (pandas), so running it here keeps those libraries
# out of the final runtime image entirely (GEN-5) — only the resulting /data is
# copied forward.
FROM 533267185808.dkr.ecr.us-west-2.amazonaws.com/docker.io/central/library/python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 AS data-build

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install the build-only dependency group (pandas, matplotlib, pillow) from the
# lock. Only pandas is needed here — the extractor imports it — but the whole
# group is installed for simplicity; matplotlib/pillow (the plotting stack) are
# harmless in this throwaway stage and never reach the runtime image.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-emit-project --only-group build -o build-requirements.txt \
    && uv pip install --system --no-cache -r build-requirements.txt

# The extractor downloads the ZFIN TSVs, joins them, and writes
# image_metadata.json. Done at build time so the container is self-contained —
# no runtime data volume to mount; refresh the data by rebuilding. The unused
# .tsv export and the intermediate TSVs are removed to keep the artifact small.
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
    && rm -rf /tmp/zfin_data /data/image_metadata.tsv

FROM 533267185808.dkr.ecr.us-west-2.amazonaws.com/docker.io/central/library/python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GENE2IMAGE_FRONTEND_DIR=/app/frontend/dist \
    GENE2IMAGE_DATA_DIR=/data \
    PORT=8000 \
    # Enables Sentry error reporting in main.py (GEN-37). A DSN only permits
    # submitting events, so it is not a secret. Set here rather than in code so
    # local dev/pytest never report; override to "" at deploy time to disable.
    SENTRY_DSN=https://bf942a1926b7aa1ad6c094f5680c71e6@o4508060872409088.ingest.us.sentry.io/4511889801740288
# The Thisse image index is copied from the data-build stage into /data, so
# GENE2IMAGE_DATA_DIR has an in-image default and no runtime volume is needed.

RUN pip install --no-cache-dir uv

# Install runtime deps first from the lock so this layer stays cached until
# uv.lock changes. --no-dev excludes the dev and build-only groups, so the heavy
# extractor/plotting libraries (pandas, matplotlib, pillow) never ship in the
# runtime image. uv export honors the lock (uv pip install . would not, it
# re-resolves from pyproject.toml); the pinned requirements give reproducible
# builds. Source is copied afterward so edits don't bust the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt

# Then copy source and install only the local package; deps already installed.
COPY backend/ ./backend/
RUN uv pip install --system --no-cache --no-deps .

# Copy the baked index from the data-build stage — none of the build-only deps
# come with it, keeping the runtime image lean.
COPY --from=data-build /data /data

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
