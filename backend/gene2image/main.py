"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .data_loader import load_data
from .routes import router

# Report unhandled exceptions to Sentry (GEN-37). The Starlette/FastAPI
# integrations are enabled automatically because fastapi is installed, so
# route errors arrive with request context attached. Gated on SENTRY_DSN,
# which only the deployed image sets (see Dockerfile) — local dev servers and
# pytest runs stay out of Sentry unless a developer exports it deliberately.
_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        # Include request headers and client IP on events. Sentry's default
        # event scrubber still redacts sensitive keys (authorization, cookies,
        # tokens), so prod's basic-auth header is filtered before upload.
        send_default_pii=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data = load_data()
    yield


app = FastAPI(title="gene2image API", lifespan=lifespan)

# Content-Security-Policy tuned to the built SPA (GEN-6):
#  - script-src allows 'self' (Vite's hashed module bundles), the Plausible
#    analytics script, and 'unsafe-inline' — index.html ships a small inline
#    Plausible bootstrap, so inline is permitted to avoid a CSP violation;
#    tightening to a nonce/hash would require build-time CSP injection.
#  - style-src allows inline styles (React style props / injected <style>).
#  - img-src allows same-origin (images are served through /api/image-proxy),
#    data: URIs, and https://zfin.org for any direct ZFIN hotlink.
#  - font-src allows 'self' and data: — the JetBrains Mono webfonts are
#    base64-inlined as data: URIs in the built CSS.
#  - connect-src allows the same-origin API, the Plausible event beacon, and
#    the Sentry ingest endpoint — @sentry/react POSTs error envelopes there
#    from the browser (GEN-37); without it the CSP silently drops every event.
#  - frame-ancestors 'none' backs up X-Frame-Options: DENY (clickjacking).
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://plausible.io; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://zfin.org; "
    "font-src 'self' data:; "
    "connect-src 'self' https://plausible.io "
    "https://o4508060872409088.ingest.us.sentry.io; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Attach baseline security headers to every response — API and static files.

    Uses setdefault so a route that already sets one of these (e.g. the image
    proxy sets X-Content-Type-Options) is not overwritten and no header is
    duplicated. The deployed OIDC/nginx layer only injects a request header
    (Authorization); it does not set these response headers, so there is no
    conflict (GEN-6).
    """
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response

# The Vite dev server (:5173) calls the API cross-origin during local
# development. Deployed containers serve the built frontend same-origin
# (GENE2IMAGE_FRONTEND_DIR is set in the image), so these localhost origins are
# only needed — and only trusted — when the frontend is NOT mounted. Excluding
# them from deployed environments keeps prod from trusting a localhost page.
_LOCAL_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _cors_allow_origins() -> list[str]:
    if os.environ.get("GENE2IMAGE_FRONTEND_DIR"):
        return []
    return list(_LOCAL_DEV_ORIGINS)


# Deploy targets are wildcard subdomains, which allow_origins (exact match
# only) can't express — Starlette fullmatches this regex against the Origin
# header and echoes back the specific origin. https only; no credentials.
_ALLOWED_ORIGIN_REGEX = (
    r"https://[A-Za-z0-9-]+\."
    r"(apps-staging\.czbiohub\.org"
    r"|apps\.czbiohub\.org"
    r"|dev-biohub\.dev\.czi\.team"
    r"|staging-biohub\.staging\.czi\.team"
    r"|prod-biohub\.prod\.czi\.team)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)

def _maybe_mount_frontend(app: FastAPI) -> None:
    frontend_dir = os.environ.get("GENE2IMAGE_FRONTEND_DIR")
    if not frontend_dir:
        return
    frontend_path = Path(frontend_dir).resolve()
    if not frontend_path.is_dir():
        raise RuntimeError(
            f"GENE2IMAGE_FRONTEND_DIR must be an existing directory: {frontend_dir}"
        )
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


_maybe_mount_frontend(app)
