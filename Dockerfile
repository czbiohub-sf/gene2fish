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

COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
RUN uv pip install --system --no-cache .

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
