FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GENE2IMAGE_FRONTEND_DIR=/app/frontend/dist \
    PORT=8000

RUN pip install --no-cache-dir uv

# Install third-party deps first from the lock so this layer stays cached
# until uv.lock changes. uv export honors the lock (uv pip install . would not,
# it re-resolves from pyproject.toml); the pinned requirements give reproducible
# builds. Source is copied afterward so edits don't bust the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt

# Then copy source and install only the local package; deps already installed.
COPY backend/ ./backend/
RUN uv pip install --system --no-cache --no-deps .

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Drop root: run as a non-privileged user. The app only reads /app and the
# read-only /data mount, and binds the non-privileged port 8000, so no root
# capability is needed at runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec uvicorn gene2image.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
